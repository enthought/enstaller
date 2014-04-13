# Author: Ilan Schnell <ischnell@enthought.com>
"""\
egginst is a simple tool for installing and uninstalling eggs. Example:

    egginst nose-1.3.0-1.egg

This tool is simple and does not care if the eggs it installs are for the
correct platform, its dependencies installed, etc... You should generally use
enpkg or Canopy's package manager instead to deal with dependencies correctly.
"""
from __future__ import absolute_import, print_function

import argparse
import ConfigParser
import cStringIO
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import warnings
import zipfile

from os.path import abspath, basename, dirname, join, isdir, isfile, normpath, sep
from uuid import uuid4

try:
    import appinst
except ImportError:  # pragma: no cover
    appinst = None

from enstaller import __version__

from . import eggmeta
from . import scripts

from .links import create_link
from .utils import (on_win, bin_dir_name, rel_site_packages, human_bytes,
                    ensure_dir, rm_empty_dir, rm_rf, get_executable, makedirs,
                    is_zipinfo_symlink, is_zipinfo_dir, zip_has_arcname)
from .utils import ZipFile

EGG_INFO = "EGG-INFO"

R_EGG_INFO = re.compile("^{0}".format(EGG_INFO))
R_EGG_INFO_BLACK_LIST = re.compile(
        "^{0}/(usr|spec|PKG-INFO.bak|prefix|.gitignore|"
        "inst|post_egginst.py|pre_egguninst.py)".format(EGG_INFO))
R_LEGACY_EGG_INFO = re.compile("(^.+.egg-info)")

PY_PAT = re.compile(r'^(.+)\.py(c|o)?$')
SO_PAT = re.compile(r'^lib.+\.so')
PY_OBJ = '.pyd' if on_win else '.so'

def name_version_fn(fn):
    """
    Given the filename of a package, returns a tuple(name, version).
    """
    if fn.endswith('.egg'):
        fn = fn[:-4]
    if '-' in fn:
        return tuple(fn.split('-', 1))
    else:
        return fn, ''

def is_in_legacy_egg_info(f, is_custom_egg):
    """
    Filter out files in legacy egg-info directory, i.e. for eggs as follows:

        package/__init__.py
        EGG-INFO/...
        package.egg-info/...

    filter out the content of package.egg-info. Only a few eggs were produced
    as above. This version of enstaller will simply copy the required content
    from EGG-INFO where setuptools expects it.
    """
    if is_custom_egg:
        if R_LEGACY_EGG_INFO.search(f):
            return True
        else:
            return False
    else:
        return False

def should_copy_in_egg_info(f, is_custom_egg):
    """
    Return True if the given archive name needs to be copied in to
    $site-packages/$package_egg_info
    """
    if R_EGG_INFO.search(f):
        if is_custom_egg:
            if R_EGG_INFO_BLACK_LIST.search(f):
                return False
            else:
                return True
        else:
            return True
    else:
        return False

def has_legacy_egg_info_format(arcnames, is_custom_egg):
    if is_custom_egg:
        for name in arcnames:
            if R_LEGACY_EGG_INFO.search(name):
                return True
        return False
    else:
        return False


def should_mark_executable(arcname, fn):
    if (arcname.startswith(('EGG-INFO/usr/bin/', 'EGG-INFO/scripts/')) or
            fn.endswith(('.dylib', '.pyd', '.so')) or
            (arcname.startswith('EGG-INFO/usr/lib/') and
             SO_PAT.match(fn))):
        return True
    else:
        return False


def should_skip(zp, arcname):
    m = PY_PAT.match(arcname)
    if m and zip_has_arcname(zp, m.group(1) + PY_OBJ):
        # .py, .pyc, .pyo next to .so are not written
        return True
    else:
        return False

def setuptools_egg_info_dir(path):
    """
    Return the .egg-info directory name as created/expected by setuptools
    """
    filename = basename(path)
    name, version = name_version_fn(filename)
    return "{0}-{1}.egg-info".format(name, version)


def install_app(meta_dir, prefix):
    return _install_app_impl(meta_dir, prefix, remove=False)


def remove_app(meta_dir, prefix):
    return _install_app_impl(meta_dir, prefix, remove=True)


def _install_app_impl(meta_dir, prefix, remove=False):
    if appinst is None:
        return

    path = join(meta_dir, eggmeta.APPINST_PATH)
    if not isfile(path):
        return

    if remove:
        try:
            try:
                appinst.uninstall_from_dat(path, prefix)
            except TypeError:
                # Old appinst (<= 2.1.1) did not handle the prefix argument (2d
                # arg)
                appinst.uninstall_from_dat(path)
        except Exception as e:
            print("Warning (uninstalling application item):\n%r" % (e,))
    else:
        try:
            try:
                appinst.install_from_dat(path, prefix)
            except TypeError:
                # Old appinst (<= 2.1.1) did not handle the prefix argument (2d
                # arg)
                appinst.install_from_dat(path)
        except Exception as e:
            print("Warning (installing application item):\n%r" % (e,))


def _run_script(meta_dir, fn, prefix):
    path = join(meta_dir, fn)
    if not isfile(path):
        return
    subprocess.call([scripts.executable, '-E', path, '--prefix', prefix],
                    cwd=dirname(path))


class _EggInstRemove(object):

    def __init__(self, path, prefix=sys.prefix, evt_mgr=None, verbose=False,
                 noapp=False):
        self.path = path
        self.fn = basename(path)
        name, version = name_version_fn(self.fn)
        self.cname = name.lower()
        self.prefix = abspath(prefix)
        self.evt_mgr = evt_mgr
        self.noapp = noapp

        self.egginfo_dir = join(self.prefix, 'EGG-INFO')
        self.meta_dir = join(self.egginfo_dir, self.cname)

        self.verbose = verbose

    def _read_uninstall_metadata(self):
        d = read_meta(self.meta_dir)

        files = [join(self.prefix, f) for f in d['files']]
        installed_size = d['installed_size']

        return installed_size, files

    def _rm_dirs(self, files):
        dir_paths = set()
        len_prefix = len(self.prefix)
        for path in set(dirname(p) for p in files):
            while len(path) > len_prefix:
                dir_paths.add(path)
                path = dirname(path)

        for path in sorted(dir_paths, key=len, reverse=True):
            if not path.rstrip(sep).endswith('site-packages'):
                rm_empty_dir(path)

    def remove_iterator(self):
        """
        Create an iterator that will remove every installed file.

        Example::

            from egginst.console import ProgressManager

            progress = ProgressManager(...)
            egginst = EggInst(...)

            with progress:
                for i, filename in self.remove_iterator():
                    print("removing file {0}".format(filename))
                    progress(step=i)
        """
        if not isdir(self.meta_dir):
            print("Error: Can't find meta data for:", self.cname)
            return

        if not self.noapp:
            remove_app(self.meta_dir, self.prefix)
        _run_script(self.meta_dir, 'pre_egguninst.py', self.prefix)

        installed_size, files = self._read_uninstall_metadata()

        for n, p in enumerate(files):
            n += 1

            rm_rf(p)
            if p.endswith('.py'):
                rm_rf(p + 'c')

            yield p

        self._rm_dirs(files)
        rm_rf(self.meta_dir)
        rm_empty_dir(self.egginfo_dir)

    def remove(self):
        if self.evt_mgr:
            from encore.events.api import ProgressManager
        else:
            from .console import ProgressManager

        installed_size, files = self._read_uninstall_metadata()

        progress = ProgressManager(
                self.evt_mgr, source=self,
                operation_id=uuid4(),
                message="removing egg",
                steps=len(files),
                # ---
                progress_type="removing", filename=self.fn,
                disp_amount=human_bytes(installed_size),
                super_id=getattr(self, 'super_id', None))

        with progress:
            for n, filename in enumerate(self.remove_iterator()):
                progress(step=n)


class EggInst(object):

    def __init__(self, path, prefix=sys.prefix, hook=False, pkgs_dir=None,
                 evt_mgr=None, verbose=False, noapp=False):
        self.path = path
        self.fn = basename(path)
        name, version = name_version_fn(self.fn)
        self.cname = name.lower()
        self.prefix = abspath(prefix)
        self.evt_mgr = evt_mgr
        self.noapp = noapp

        self.bin_dir = join(self.prefix, bin_dir_name)

        if self.prefix != abspath(sys.prefix):
            scripts.executable = get_executable(self.prefix)

        self.site_packages = join(self.prefix, rel_site_packages)
        self.pyloc = self.site_packages
        self.egginfo_dir = join(self.prefix, 'EGG-INFO')
        self.meta_dir = join(self.egginfo_dir, self.cname)

        self.meta_json = join(self.meta_dir, 'egginst.json')
        self.files = []
        self.verbose = verbose

        self._egginst_remover = _EggInstRemove(path, prefix, evt_mgr, verbose, noapp)
        self._installed_size = None
        self._files_to_install = None

    @property
    def installed_size(self):
        """
        Return the size (bytes) of the extracted egg.
        """
        if self._installed_size is None:
            with ZipFile(self.path) as zp:
                self._installed_size = sum(zp.getinfo(name).file_size for name
                                           in zp.namelist())
        return self._installed_size

    def iter_files_to_install(self):
        return self._lines_from_arcname('EGG-INFO/inst/files_to_install.txt')

    def iter_targets(self):
        return self._lines_from_arcname('EGG-INFO/inst/targets.dat')

    def _should_create_info(self):
        for arcname in ('EGG-INFO/spec/depend', 'EGG-INFO/info.json'):
            if zip_has_arcname(self.z, arcname):
                return True
        return False

    def install(self, extra_info=None):

        if not isdir(self.meta_dir):
            os.makedirs(self.meta_dir)

        self.z = zipfile.ZipFile(self.path)
        try:
            self.extract()

            if on_win:
                scripts.create_proxies(self)
            else:
                from . import object_code
                if self.verbose:
                    object_code.verbose = True
                object_code.fix_files(self)

                self._create_links()

            self._entry_points()
            if self._should_create_info():
                eggmeta.create_info(self, extra_info)
        finally:
            self.z.close()

        scripts.fix_scripts(self)
        if not self.noapp:
            install_app(self.meta_dir, self.prefix)
        self._write_meta()

        _run_script(self.meta_dir, 'post_egginst.py', self.prefix)

    def _create_links(self):
        """
        Given the content of the EGG-INFO/inst/files_to_install.txt file,
        create/remove the links listed therein.
        """
        for line in self.iter_files_to_install():
            arcname, link = line.split()
            if link == 'False':
                continue
            self.files.append(create_link(arcname, link, self.prefix, self.verbose))

    def _entry_points(self):
        lines = list(self._lines_from_arcname('EGG-INFO/entry_points.txt',
                                             ignore_empty=False))
        if lines == []:
            return
        conf = ConfigParser.ConfigParser()
        conf.readfp(cStringIO.StringIO('\n'.join(lines) + '\n'))
        if ('console_scripts' in conf.sections() or
                'gui_scripts' in conf.sections()):
            if self.verbose:
                print('creating scripts')
                scripts.verbose = True
            scripts.create(self, conf)


    def _rel_prefix(self, path):
        return abspath(path).replace(self.prefix, '.').replace('\\', '/')

    def _write_meta(self):
        d = dict(
            egg_name = self.fn,
            prefix = self.prefix,
            installed_size = self.installed_size,
            files = [self._rel_prefix(p)
                           if abspath(p).startswith(self.prefix) else p
                     for p in self.files + [self.meta_json]]
        )
        with open(self.meta_json, 'w') as f:
            json.dump(d, f, indent=2, sort_keys=True)

    def _lines_from_arcname(self, arcname, ignore_empty=True):
        if zip_has_arcname(self.z, arcname):
            for line in self.z.read(arcname).splitlines():
                line = line.strip()
                if ignore_empty and line == '':
                    continue
                if line.startswith('#'):
                    continue
                yield line

    def archive_extractor(self):
        """
        Create an iterator that will extract over each archive to be extracted.

        Example::

            from egginst.console import ProgressManager

            progress = ProgressManager(...)
            egginst = EggInst(...)

            with progress:
                for n in self.archive_extractor():
                    progress(step=n)
        """
        arcnames = self.z.namelist()
        is_custom_egg = eggmeta.is_custom_egg(self.path)

        use_legacy_egg_info_format = has_legacy_egg_info_format(arcnames,
                                                                is_custom_egg)

        n = 0
        for arcname in arcnames:
            if use_legacy_egg_info_format:
                n += self._extract_egg_with_legacy_egg_info(arcname,
                                                               is_custom_egg)
            else:
                n += self._extract(arcname, is_custom_egg)
            yield n


    def extract(self):
        if self.evt_mgr:
            from encore.events.api import ProgressManager
        else:
            from .console import ProgressManager

        progress = ProgressManager(
                self.evt_mgr, source=self,
                operation_id=uuid4(),
                message="installing egg",
                steps=self.installed_size,
                # ---
                progress_type="installing", filename=self.fn,
                disp_amount=human_bytes(self.installed_size),
                super_id=getattr(self, 'super_id', None))

        with progress:
            for currently_extracted_size in self.archive_extractor():
                progress(step=currently_extracted_size)

    def _extract_egg_with_legacy_egg_info(self, name, is_custom_egg):
        zip_info = self.z.getinfo(name)

        if is_in_legacy_egg_info(name, is_custom_egg):
            self._write_legacy_egg_info_metadata(zip_info)
        else:
            self._write_arcname(name)

        return zip_info.file_size

    def _extract(self, name, is_custom_egg):
        zip_info = self.z.getinfo(name)

        self._write_arcname(name)
        if should_copy_in_egg_info(name, is_custom_egg):
            self._write_standard_egg_info_metadata(zip_info)

        return zip_info.file_size

    def _write_legacy_egg_info_metadata(self, zip_info):
        if is_zipinfo_dir(zip_info):
            return

        name = zip_info.filename
        m = R_LEGACY_EGG_INFO.search(name)
        if m:
            legacy_egg_info_dir = m.group(1)
            from_egg_info = posixpath.relpath(name, legacy_egg_info_dir)

            dest = join(self.pyloc, setuptools_egg_info_dir(self.path),
                        from_egg_info)
            self._write_egg_info_arcname(name, dest)
        else:
            raise ValueError(
                    "BUG: Unexpected name for legacy egg info in {0}: {1}". \
                    format(self.fn, name))

    def _write_standard_egg_info_metadata(self, zip_info):
        if is_zipinfo_dir(zip_info):
            return

        name = zip_info.filename
        from_egg_info = posixpath.relpath(name, EGG_INFO)
        dest = posixpath.join(self.pyloc, setuptools_egg_info_dir(self.path),
                from_egg_info)

        self._write_egg_info_arcname(name, dest)

    def _write_egg_info_arcname(self, name, dest):
        ensure_dir(dest)
        source = self.z.open(name)
        try:
            with open(dest, "wb") as target:
                shutil.copyfileobj(source, target)
                self.files.append(dest)
        finally:
            source.close()


    def _get_dst(self, arcname):
        def _transform_path(arcname, egg_prefix, dest_prefix):
            return abspath(join(dest_prefix, arcname[len(egg_prefix):]))

        if on_win:
            scheme = [
                ("EGG-INFO/prefix/", self.prefix),
                ("EGG-INFO/scripts/", self.bin_dir),
                ("EGG-INFO/", self.meta_dir),
            ]
        else:
            scheme = [
                ("EGG-INFO/prefix/", self.prefix),
                ("EGG-INFO/usr/", self.prefix),
                ("EGG-INFO/scripts/", self.bin_dir),
                ("EGG-INFO/", self.meta_dir),
            ]

        for prefix, dest in scheme:
            if arcname.startswith(prefix):
                return _transform_path(arcname, prefix, dest)
        return _transform_path(arcname, "", self.pyloc)

    def _extract_symlink(self, arcname):
        link_name = self._get_dst(arcname)
        source = self.z.read(arcname)
        dirn, filename = os.path.split(link_name)
        makedirs(dirn)
        if os.path.exists(link_name):
            os.unlink(link_name)
        os.symlink(source, link_name)
        return link_name

    def _write_arcname(self, arcname):
        if arcname.endswith('/') or arcname.startswith('.unused'):
            return

        zip_info = self.z.getinfo(arcname)

        if is_zipinfo_symlink(zip_info):
            link_name = self._extract_symlink(arcname)
            self.files.append(link_name)
            return

        if should_skip(self.z, arcname):
            return

        path = self._get_dst(arcname)
        ensure_dir(path)

        self.files.append(path)

        with open(path, "wb") as fo:
            shutil.copyfileobj(self.z.open(arcname), fo)

        if should_mark_executable(arcname, path):
            os.chmod(path, 0o755)

    def remove(self):
        self._egginst_remover.remove()


def read_meta(meta_dir):
    meta_json = join(meta_dir, 'egginst.json')
    if isfile(meta_json):
        return json.load(open(meta_json))
    return None


def get_installed(prefix=sys.prefix):
    """
    Generator returns a sorted list of all installed packages.
    Each element is the filename of the egg which was used to install the
    package.
    """
    egg_info_dir = join(prefix, 'EGG-INFO')
    if not isdir(egg_info_dir):
        return
    pat = re.compile(r'([a-z0-9_.]+)$')
    for fn in sorted(os.listdir(egg_info_dir)):
        if not pat.match(fn):
            continue
        d = read_meta(join(egg_info_dir, fn))
        if d is None:
            continue
        yield d['egg_name']


def print_installed(prefix=sys.prefix):
    fmt = '%-20s %s'
    print(fmt % ('Project name', 'Version'))
    print(40 * '=')
    for fn in get_installed(prefix):
        print(fmt % name_version_fn(fn))


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]  # pragma: no cover

    p = argparse.ArgumentParser(usage="usage: %(prog)s [options] [EGGS ...]",
                                description=__doc__,
                                formatter_class=argparse.RawTextHelpFormatter)

    p.add_argument("requirements", help="Requirements to install", nargs='*')

    p.add_argument('-l', "--list",
                 action="store_true",
                 help="list all installed packages")

    p.add_argument("--noapp",
                 action="store_true",
                 help="don't install/remove application menu items")

    p.add_argument("--prefix",
                 action="store",
                 default=sys.prefix,
                 help="install prefix",
                 metavar='PATH')

    p.add_argument("--pkgs-dir",
                 action="store",
                 help="Do nothing, kept for backward compatibility.",
                 metavar='PATH')

    p.add_argument('-r', "--remove",
                 action="store_true",
                 help="remove package(s), requires the egg or project name(s)")

    p.add_argument('-v', "--verbose", action="store_true")
    p.add_argument('--version', action="store_true")

    ns = p.parse_args(argv)
    if ns.version:
        print("enstaller version:", __version__)
        return

    prefix = normpath(abspath(ns.prefix))
    if prefix != normpath(sys.prefix):
        warnings.warn("Using the --prefix option is potentially dangerous. "
                      "You should use enpkg installed in {0} instead.". \
                      format(ns.prefix))

    if ns.list:
        print_installed(prefix)
        return

    evt_mgr = None

    for path in ns.requirements:
        print(path)
        ei = EggInst(path, prefix, False, ns.pkgs_dir, evt_mgr,
                     verbose=ns.verbose, noapp=ns.noapp)
        if ns.remove:
            ei.remove()
        else: # default is always install
            ei.install()


if __name__ == '__main__': # pragma: no cover
    main()
