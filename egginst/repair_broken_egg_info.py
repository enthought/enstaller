from __future__ import print_function

import argparse
import os.path
import shutil
import sys

from egginst import logger
from egginst.main import (EggInst, get_installed, setuptools_egg_info_dir,
                          should_copy_in_egg_info)
from egginst.utils import makedirs, rm_rf


def package_egg_info_dir(egginst):
    return os.path.join(egginst.site_packages, setuptools_egg_info_dir(egginst.path))


def convert_path_to_posix(p):
    if os.path.sep != "/":
        return p.replace(os.path.sep, "/")
    else:
        return p


class EggInfoDirFixer(object):
    def __init__(self, egg, prefix=sys.prefix, dry_run=False):
        self._egginst = EggInst(egg, prefix=prefix)
        self.egg_info_dir = package_egg_info_dir(self._egginst)
        self.dry_run = dry_run

    def needs_repair(self):
        if not os.path.exists(self.egg_info_dir):
            return False
        if os.path.isdir(self.egg_info_dir):
            egg_info_dir_content = os.listdir(self.egg_info_dir)
            if "PKG-INFO" in egg_info_dir_content or "egginst.json" in egg_info_dir_content:
                return False
            return True
        elif os.path.isfile(self.egg_info_dir):
            return True

    def repair(self):
        source_egg_info_dir = self._egginst.meta_dir
        dest_egg_info_dir = package_egg_info_dir(self._egginst)

        _repair_package_dir(source_egg_info_dir, dest_egg_info_dir, self.dry_run)


def _in_place_repair(source_egg_info_dir, dest_egg_info_dir, dry_run):
    """
    Repair the given destination .egg-info directory using the given source
    egg-info directory.

    Parameters
    ----------
    source_egg_info_dir: str
        The full path to source directory (e.g.
        '...\\EGG-INFO\\<package_name>')
    dest_egg_info_dir: str
        The full path to target directory (e.g.
        '...\\site-package\\<package_name>-<version>.egg-info')
    dry_run: bool
        If True, no file is written.
    """
    makedirs(dest_egg_info_dir)
    for root, dirs, files in os.walk(source_egg_info_dir):
        for f in files:
            path = os.path.relpath(os.path.join(root, f), source_egg_info_dir)
            path = os.path.join("EGG-INFO", path)
            if should_copy_in_egg_info(convert_path_to_posix(path), True):
                source = os.path.join(root, f)
                target = os.path.join(dest_egg_info_dir,
                                      os.path.relpath(source, source_egg_info_dir))
                if dry_run:
                    logger.dry_run.info("Would copy %r to %r", source, target)
                else:
                    shutil.copy(source, target)


def _fix_pkg_info_file(egg_info_file, dest_egg_info_dir, dry_run):
    if not os.path.exists(egg_info_file):
        return
    if not os.path.isfile(egg_info_file):
        return

    source_pkg_info = egg_info_file
    target_pkg_info = os.path.join(dest_egg_info_dir, "PKG-INFO")

    if dry_run:
        logger.dry_run.info("Would copy %r to %r", source_pkg_info, target_pkg_info)
    else:
        shutil.copy(source_pkg_info, target_pkg_info)


def _repair_package_dir(source_egg_info_dir, dest_egg_info_dir, dry_run):
    if dry_run:
        _in_place_repair(source_egg_info_dir, dest_egg_info_dir, dry_run)
        _fix_pkg_info_file(dest_egg_info_dir, dest_egg_info_dir, dry_run)
        return

    working_dir = dest_egg_info_dir + ".wdir"
    temp_dir = dest_egg_info_dir + ".bak"

    # We do the transformation in a temporary directory we then move to the
    # final destination to avoid putting stalled .egg-info directories.
    makedirs(working_dir)
    try:
        _in_place_repair(source_egg_info_dir, working_dir, dry_run)
        _fix_pkg_info_file(dest_egg_info_dir, working_dir, dry_run)
        # Backup original egg-info file/dir
        os.rename(dest_egg_info_dir, temp_dir)
        # Move repaired egg-info file/dir to final destination
        os.rename(working_dir, dest_egg_info_dir)
    except BaseException:
        rm_rf(working_dir)
    else:
        rm_rf(temp_dir)


def repair(prefix, dry_run):
    """
    Repair every Enthought egg installed in the given prefix

    Parameters
    ----------
    prefix: str
        The prefix to repair
    dry_run: bool
        If True, the egg-info directory is not modified
    """
    for egg in get_installed(prefix):
        fixer = EggInfoDirFixer(egg, prefix, dry_run=dry_run)
        if fixer.needs_repair():
            fixer.repair()


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    p = argparse.ArgumentParser(description="Script to repair '.egg-info' directories.")
    p.add_argument("-n", "--dry-run", help="Do not modify anything", action="store_true")
    p.add_argument("--prefix", help="The prefix to fix (default: '%(default)s')",
                   default=os.path.normpath(sys.prefix))
    ns = p.parse_args(argv)

    prefix = ns.prefix
    if not os.path.exists(prefix):
        p.error("Prefix {0} does not exist".format(prefix))

    repair(prefix, ns.dry_run)
