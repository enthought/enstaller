import argparse
import os
import os.path
import sys

from okonomiyaki.errors import OkonomiyakiError
from okonomiyaki.file_formats.egg import (_SPEC_DEPEND_LOCATION,
                                          LegacySpecDepend, is_egg_name_valid,
                                          split_egg_name)
from okonomiyaki.file_formats.setuptools_egg import parse_filename
from okonomiyaki.platforms.legacy import LegacyEPDPlatform

from egginst._zipfile import ZipFile
from enstaller.errors import EnstallerException


ENDIST_DAT = "endist.dat"

_SETUPTOOLS_TYPE = "setuptools"
_EGGINST_TYPE = "egginst"


def _looks_like_enthought_egg(path):
    """ Returns True if the give file looks like an enthought egg.
    """
    filename = os.path.basename(path)

    if is_egg_name_valid(filename):
        with ZipFile(path) as zp:
            try:
                zp.getinfo(_SPEC_DEPEND_LOCATION)
                return True
            except KeyError:
                pass

    return False


def _looks_like_setuptools_egg(path):
    filename = os.path.basename(path)

    try:
        parse_filename(filename)
        return True
    except OkonomiyakiError:
        return False


def _get_spec(source_egg_path, build_number, platform_string=None):
    if _looks_like_setuptools_egg(source_egg_path):
        name, version, pyver, _ = parse_filename(os.path.basename(source_egg_path))
    elif _looks_like_enthought_egg(source_egg_path):
        name, version, _ = split_egg_name(os.path.basename(source_egg_path))
        pyver = None

    data = {"build": build_number, "packages": [], "name": name,
            "version": version}

    if platform_string is None:
        try:
            epd_platform = LegacyEPDPlatform.from_running_system()
        except OkonomiyakiError as e:
            msg = "Could not guess platform from system (original " \
                  "error was {0!r}). " \
                  "You may have to specify the platform explicitly."
            raise EnstallerException(msg.format(e))
    else:
        epd_platform = \
            LegacyEPDPlatform.from_epd_platform_string(platform_string)

    return LegacySpecDepend.from_data(data, epd_platform.short, pyver)


def repack(source_egg_path, build_number=1, platform_string=None):
    legacy_spec = _get_spec(source_egg_path, build_number, platform_string)

    parent_dir = os.path.dirname(os.path.abspath(source_egg_path))
    target_egg_path = os.path.join(parent_dir, legacy_spec.egg_name)

    if os.path.exists(target_egg_path) and \
            os.path.samefile(source_egg_path, target_egg_path):
        msg = "source and repack-ed egg are the same file: {0!r}. Inplace " \
              "mode not yet implemented."
        raise EnstallerException(msg.format(source_egg_path))

    # XXX: implement endist.dat/app handling

    print(20 * '-' + '\n' + legacy_spec.to_string() + 20 * '-')

    with ZipFile(source_egg_path) as source:
        with ZipFile(target_egg_path, "w") as target:
            for archive in source.namelist():
                if archive in (_SPEC_DEPEND_LOCATION):
                    continue
                target.writestr(source.getinfo(archive), source.read(archive))

            target.writestr(_SPEC_DEPEND_LOCATION, legacy_spec.to_string())


def main(argv=None):
    argv = argv or sys.argv[1:]

    p = argparse.ArgumentParser("Egg repacker.")
    p.add_argument("egg", help="Path to the egg to repack.")
    p.add_argument("-b", "--build", dest="build_number",
                   help="Build number (default is %(default)s)",
                   default=1, type=int)
    p.add_argument("-a", dest="platform_string",
                   help="Legacy epd platform string (e.g. 'rh5-32'). "
                        "Will be guessed if not specified.")
    ns = p.parse_args(argv)

    if os.path.exists(ENDIST_DAT):
        p.error("{0!r} files are not handled yet.".format(ENDIST_DAT))

    repack(ns.egg, ns.build_number, ns.platform_string)


if __name__ == "__main__":
    main()
