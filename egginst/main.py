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
import json
import logging
import os
import posixpath
import re
import shutil
import subprocess
import sys
import warnings

from os.path import abspath, basename, dirname, join, isdir, isfile, normpath, sep

try:
    import appinst
except ImportError:  # pragma: no cover
    appinst = None

from . import eggmeta
from . import object_code
from . import scripts

from .links import create_link
from .progress import console_progress_manager_factory
from .utils import (on_win, bin_dir_name, rel_site_packages, ensure_dir,
                    rm_empty_dir, rm_rf, get_executable, is_zipinfo_dir,
                    zip_has_arcname)
from ._zipfile import ZipFile

from .vendor.six import StringIO
from .vendor.six.moves import configparser

EGG_INFO = "EGG-INFO"
BOOTSTRAP_ARCNAME = EGG_INFO + "/spec/__bootstrap__.py"

R_EGG_INFO = re.compile("^{0}".format(EGG_INFO))
R_EGG_INFO_BLACK_LIST = re.compile(
    "^{0}/(usr|spec|PKG-INFO.bak|prefix|.gitignore|"
    "inst|post_egginst.py|pre_egguninst.py)".format(EGG_INFO))
R_LEGACY_EGG_INFO = re.compile("(^.+.egg-info)")

PY_PAT = re.compile(r'^(.+)\.py(c|o)?$')
SO_PAT = re.compile(r'^lib.+\.so')
PY_OBJ = '.pyd' if on_win else '.so'

logger = logging.getLogger(__name__)


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
    if os.path.islink(fn):
        return False
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
        handler = appinst.uninstall_from_dat
        warning = 'uninstalling application item'
    else:
        handler = appinst.install_from_dat
        warning = 'installing application item'

    try:
        try:
            handler(path, prefix)
        except TypeError:
            # Old appinst (<= 2.1.1) did not handle the prefix argument (2d
            # arg)
            handler(path)
    except Exception as e:
        logger.warn("Warning ({0}):\n{1!r}".format(warning, e))


def _run_script(meta_dir, fn, prefix):
    path = join(meta_dir, fn)
    if not isfile(path):
        return
    subprocess.call([scripts.executable, '-E', path, '--prefix', prefix],
                    cwd=dirname(path))


class _EggInstRemove(object):

    def __init__(self, path, prefix=sys.prefix, noapp=False):
        self.path = path
        self.fn = basename(path)
        name, version = name_version_fn(self.fn)
        self.cname = name.lower()
        self.prefix = abspath(prefix)
        self.noapp = noapp

        self.egginfo_dir = join(self.prefix, 'EGG-INFO')
        self.meta_dir = join(self.egginfo_dir, self.cname)

        self._files = None
        self._installed_size = None

    @property
    def is_installed(self):
        return isdir(self.meta_dir)

    @property
    def files(self):
        if self._files is None:
            self._read_uninstall_metadata()
        return self._files

    @property
    def installed_size(self):
        if self._installed_size is None:
            self._read_uninstall_metadata()
        return self._installed_size

    def _read_uninstall_metadata(self):
        d = read_meta(self.meta_dir)

        self._files = [join(self.prefix, f) for f in d['files']]
        self._installed_size = d['installed_size']

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
        if not self.is_installed:
            logger.error("Error: Can't find meta data for: {0!r}".
                         format(self.cname))
            return

        if not self.noapp:
            remove_app(self.meta_dir, self.prefix)
        _run_script(self.meta_dir, 'pre_egguninst.py', self.prefix)

        for n, p in enumerate(self.files):
            n += 1

            rm_rf(p)
            if p.endswith('.py'):
                rm_rf(p + 'c')
                rm_rf(p + 'o')

            yield p

        self._rm_dirs(self.files)
        rm_rf(self.meta_dir)
        rm_empty_dir(self.egginfo_dir)

    def remove(self):
        for filename in self.remove_iterator():
            pass


class EggInst(object):

    def __init__(self, path, prefix=sys.prefix, hook=False, pkgs_dir=None,
                 noapp=False):
        self.path = path
        self.fn = basename(path)
        name, version = name_version_fn(self.fn)
        self.cname = name.lower()
        self.prefix = abspath(prefix)
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

        self._egginst_remover = _EggInstRemove(path, prefix, noapp)
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

    def pre_extract(self):
        if not isdir(self.meta_dir):
            os.makedirs(self.meta_dir)

    def post_extract(self, extra_info=None):
        with ZipFile(self.path) as zp:
            self.z = zp

            if on_win:
                scripts.create_proxies(self)
            else:
                # XXX: we ignore placeholder hack for enstaller, to avoid error
                # messages related to tests data when updating enstaller
                # (enstaller test data contain some osx/linux binaries)
                if self.cname != "enstaller":
                    object_code.apply_placeholder_hack(self.files,
                                                       list(self.iter_targets()),
                                                       self.prefix)

                self._create_links()

            self._entry_points()
            if self._should_create_info():
                eggmeta.create_info(self, extra_info)

        scripts.fix_scripts(self)

        if not self.noapp:
            install_app(self.meta_dir, self.prefix)

        self._write_meta()

        _run_script(self.meta_dir, 'post_egginst.py', self.prefix)

    def install(self, extra_info=None):
        for currently_extracted_size in self.install_iterator():
            pass

    def _create_links(self):
        """
        Given the content of the EGG-INFO/inst/files_to_install.txt file,
        create/remove the links listed therein.
        """
        for line in self.iter_files_to_install():
            arcname, link = line.split()
            if link == 'False':
                continue
            self.files.append(create_link(arcname, link, self.prefix))

    def _entry_points(self):
        lines = list(self._lines_from_arcname('EGG-INFO/entry_points.txt',
                                              ignore_empty=False))
        if lines == []:
            return
        conf = configparser.ConfigParser()
        data = u'\n'.join(lines) + '\n'
        # XXX: hack to workaround 2.6-specific bug with ConfigParser and
        # unicode.
        if sys.version_info < (2, 7, 3):
            conf.readfp(StringIO(data.encode("utf8")))
        else:
            conf.readfp(StringIO(data))
        if ('console_scripts' in conf.sections() or
                'gui_scripts' in conf.sections()):
            logger.debug('creating scripts')
            scripts.create(self, conf)

    def _rel_prefix(self, path):
        return abspath(path).replace(self.prefix, '.').replace('\\', '/')

    def _write_meta(self):
        d = dict(
            egg_name=self.fn,
            prefix=self.prefix,
            installed_size=self.installed_size,
            files=[self._rel_prefix(p)
                   if abspath(p).startswith(self.prefix) else p
                   for p in self.files + [self.meta_json]]
        )
        with open(self.meta_json, 'w') as f:
            json.dump(d, f, indent=2, sort_keys=True)

    def _lines_from_arcname(self, arcname, ignore_empty=True):
        if zip_has_arcname(self.z, arcname):
            for line in self.z.read(arcname).decode("utf8").splitlines():
                line = line.strip()
                if ignore_empty and line == '':
                    continue
                if line.startswith('#'):
                    continue
                yield line

    def install_iterator(self, extra_info=None):
        """
        Create an iterator that will iterate over each archive to be extracted.

        Example::

            from egginst.console import ProgressManager

            progress = ProgressManager(...)
            egginst = EggInst(...)

            with progress:
                for n in self.install_iterator():
                    progress(step=n)
        """
        self.pre_extract()

        with ZipFile(self.path) as zp:
            self.z = zp

            arcnames = self.z.namelist()
            is_custom_egg = eggmeta.is_custom_egg(self.path)

            use_legacy_egg_info_format = has_legacy_egg_info_format(arcnames,
                                                                    is_custom_egg)

            for arcname in arcnames:
                if use_legacy_egg_info_format:
                    n = self._extract_egg_with_legacy_egg_info(arcname,
                                                               is_custom_egg)
                else:
                    n = self._extract(arcname, is_custom_egg)
                yield n

        self.post_extract(extra_info)

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
            msg = ("BUG: Unexpected name for legacy egg info in {0}: {1}".
                   format(self.fn, name))
            raise ValueError(msg)

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

    def _write_arcname(self, arcname):
        if arcname.endswith('/') or arcname.startswith('.unused'):
            return

        if should_skip(self.z, arcname):
            return

        path = self._get_dst(arcname)
        destination = os.path.relpath(path, self.prefix)

        self.z.extract_to(arcname, destination, self.prefix)
        self.files.append(path)

        if should_mark_executable(arcname, path):
            os.chmod(path, 0o755)

    def remove(self):
        return self._egginst_remover.remove()

    def remove_iterator(self):
        return self._egginst_remover.remove_iterator()


def read_meta(meta_dir):
    meta_json = join(meta_dir, 'egginst.json')
    if isfile(meta_json):
        with open(meta_json) as fp:
            return json.load(fp)
    return None


def _read_version_string(meta_dir):
    """ Return the version string for the given meta_dir.

    Is None if the version could not be figured out (old or incompatible
    metadata).
    """
    metadata = read_meta(meta_dir)
    if metadata:
        egg_name = metadata.get("egg_name")
        if egg_name is not None:
            return name_version_fn(egg_name)[1]
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


def install_egg_cli(path, prefix, noapp=False, extra_info=None):
    """
    Simple wrapper to install an egg using default egginst progress bar.
    """
    installer = EggInst(path, prefix, False, None, noapp)

    progress = console_progress_manager_factory("installing egg", installer.fn,
                                                size=installer.installed_size)
    with progress:
        for currently_extracted_size in installer.install_iterator(extra_info):
            progress.update(currently_extracted_size)


def remove_egg_cli(path, prefix, noapp=False):
    """
    Simple wrapper to remove an egg using default egginst progress bar.
    """
    installer = EggInst(path, prefix, False, None, noapp=noapp)
    remover = installer._egginst_remover
    if not remover.is_installed:
        logger.error("Error: can't find meta data for: %r", remover.cname)
        return
    version = _read_version_string(remover.meta_dir)
    if version is not None:
        name = "{0}-{1}.egg".format(remover.cname, version)
    else:
        name = installer.fn
    progress = console_progress_manager_factory("removing egg", name,
                                                remover.installed_size,
                                                len(remover.files))
    with progress:
        for filename in remover.remove_iterator():
            progress.update(1)


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
        # Local import to avoid circular imports between enstaller and egginst
        from enstaller import __version__
        print("enstaller version:", __version__)
        return

    prefix = normpath(abspath(ns.prefix))
    if prefix != normpath(sys.prefix):
        warnings.warn("Using the --prefix option is potentially dangerous. "
                      "You should use enpkg installed in {0} instead.".
                      format(ns.prefix))

    if ns.list:
        print_installed(prefix)
        return

    if ns.verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    else:
        logging.basicConfig(level=logging.WARN, format="%(message)s")

    for path in ns.requirements:
        if ns.remove:
            remove_egg_cli(path, prefix, ns.noapp)
        else:
            install_egg_cli(path, prefix, ns.noapp)


if __name__ == '__main__':  # pragma: no cover
    main()
