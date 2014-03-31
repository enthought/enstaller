import errno
import os.path
import shutil
import sys

from egginst.main import (EggInst, get_installed, read_meta,
        setuptools_egg_info_dir, should_copy_in_egg_info)
from egginst.utils import makedirs, rm_rf


def package_egg_info_dir(egginst):
    return os.path.join(egginst.site_packages, setuptools_egg_info_dir(egginst.path))


def needs_repair(egg_info_dir):
    if not os.path.exists(egg_info_dir):
        return False
    if not os.path.isdir(egg_info_dir):
        return False
    egg_info_dir_content = os.listdir(egg_info_dir)
    if "PKG-INFO" in egg_info_dir_content or "egginst.json" in egg_info_dir_content:
        return False
    return True


def convert_path_to_posix(p):
    if os.path.sep != "/":
        return p.replace(os.path.sep, "/")


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
                    print "Would copy {0} to {1}".format(source, target)
                else:
                    shutil.copy(source, target)


def repair_package(egginst, dry_run=False):
    dest_egg_info_dir = package_egg_info_dir(egginst)
    source_egg_info_dir = egginst.meta_dir

    if dry_run:
        _in_place_repair(source_egg_info_dir, dest_egg_info_dir, dry_run)
        return

    working_dir = dest_egg_info_dir + ".wdir"
    temp_dir = dest_egg_info_dir + ".bak"

    # We do the transformation in a temporary directory we then move to the
    # final destination to avoid putting stalled .egg-info directories.
    makedirs(working_dir)
    try:
        _in_place_repair(source_egg_info_dir, working_dir, dry_run)
        os.rename(dest_egg_info_dir, temp_dir)
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
        # We use EggInst instances to get the EGG-INFO directory for each
        # package
        egginst = EggInst(egg, prefix=prefix)
        egg_info_dir = package_egg_info_dir(egginst)
        if needs_repair(egg_info_dir):
            repair_package(egginst, dry_run=dry_run)
