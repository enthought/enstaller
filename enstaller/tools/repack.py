import argparse
import os
import os.path
import re
import shutil
import sys
import tempfile


from egginst.vendor.okonomiyaki.errors import OkonomiyakiError
from egginst.vendor.okonomiyaki.file_formats import (
    Dependencies, EggBuilder, EggMetadata, PackageInfo, Requirement,
    is_egg_name_valid,
)
from egginst.vendor.okonomiyaki.file_formats.setuptools_egg import (
    _UNSPECIFIED, SetuptoolsEggMetadata, parse_filename
)
from egginst.vendor.okonomiyaki.platforms import EPDPlatform
from egginst.vendor.okonomiyaki.versions import MetadataVersion
from egginst.vendor.okonomiyaki.versions.pep386 import suggest_normalized_version

from egginst.vendor.zipfile2 import ZipFile

from egginst.eggmeta import SPEC_DEPEND_KEYS
from egginst.utils import samefile
from egginst.vendor.six import string_types

from enstaller.errors import EnstallerException
from enstaller.versions.enpkg import EnpkgVersion


DEFAULT_METADATA_VERSION = MetadataVersion(1, 3)

ENDIST_DAT = "endist.dat"
# Whitelist of keys considered when exec`ing the endist.dat to update
# spec/depend
ACCEPTED_ENDIST_SPEC_KEYS = SPEC_DEPEND_KEYS
# Whitelist of keys considered when exec`ing the endist.dat to update
# the egg content
ACCEPTED_ENDIST_EGG_KEYS = ("add_files", )
# List of endist keys not yet supported by this tool
UNSUPPORTED_ENDIST_KEYS = ("app_icon_file", "svn_rev", "svn_rev_init",
                           "no_pyc")

_SETUPTOOLS_TYPE = "setuptools"
_EGGINST_TYPE = "egginst"


class InvalidVersion(EnstallerException):
    def __init__(self, *args, **kw):
        self.version, = args
        super(InvalidVersion, self).__init__(*args, **kw)

    def __str__(self):
        suggested = suggest_normalized_version(self.version)
        template = ("The given version '{0}' does not follow PEP 386. Please "
                    "change the egg version to a valid format")
        if suggested is not None:
            template += " (e.g. '{0}').".format(suggested)
        else:
            template += "."
        return template.format(self.version)


def _looks_like_enthought_egg(path):
    """ Returns True if the give file looks like an enthought egg.
    """
    filename = os.path.basename(path)

    if is_egg_name_valid(filename):
        with ZipFile(path) as zp:
            try:
                zp.getinfo("EGG-INFO/spec/depend")
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


def _get_spec_data(source_egg_path, build_number, platform_string=None,
                   python=_UNSPECIFIED, abi_tag=_UNSPECIFIED):
    if _looks_like_setuptools_egg(source_egg_path):
        parsed_platform_string = parse_filename(source_egg_path)[3]
        if parsed_platform_string is not None and platform_string is None:
            msg = ("Platform-specific egg detected (platform string is "
                   "{0!r}), you *must* specify the platform.")
            raise EnstallerException(msg.format(parsed_platform_string))

        if platform_string is not None:
            platform = EPDPlatform.from_epd_string(platform_string)
        else:
            platform = None
        metadata = SetuptoolsEggMetadata.from_egg(
            source_egg_path, platform, python, abi_tag
        )
        egg_basename = metadata.name
        version = str(metadata.version)
        dependencies = []
    elif _looks_like_enthought_egg(source_egg_path):
        metadata = EggMetadata.from_egg(source_egg_path)
        # The name as used in spec/depend and endist.dat is the so-called
        # egg basename (i.e. not normalied to lower case)
        egg_basename = metadata.egg_basename
        version = metadata.upstream_version
        dependencies = metadata.runtime_dependencies
    else:
        msg = "Unrecognized format: {0!r}".format(source_egg_path)
        raise EnstallerException(msg)

    data = {"build": build_number, "packages": dependencies,
            "name": egg_basename, "version": version}

    if os.path.exists(ENDIST_DAT):
        data.update(_parse_endist_for_spec_depend(ENDIST_DAT))

    return data, metadata


def _raw_packages_to_requirements(packages):
    return tuple(Requirement.from_spec_string(s) for s in packages)


def _get_spec(source_egg_path, build_number, platform_string=None,
              python=_UNSPECIFIED, abi_tag=_UNSPECIFIED,
              metadata_version=None):
    data, metadata = _get_spec_data(
        source_egg_path, build_number, platform_string, python, abi_tag,
    )

    if platform_string is None:
        try:
            epd_platform = EPDPlatform.from_running_system()
        except OkonomiyakiError as e:
            msg = "Could not guess platform from system (original " \
                  "error was {0!r}). " \
                  "You may have to specify the platform explicitly."
            raise EnstallerException(msg.format(e))
    else:
        epd_platform = EPDPlatform.from_epd_string(platform_string)

    raw_name = data["name"]
    version = EnpkgVersion.from_upstream_and_build(data["version"],
                                                   data["build"])
    if version.upstream.is_worked_around:
        raise InvalidVersion(str(version.upstream))

    dependencies = Dependencies(runtime=data["packages"])
    pkg_info = PackageInfo.from_egg(source_egg_path)
    return EggMetadata(raw_name, version, epd_platform, metadata.python_tag,
                       metadata.abi_tag, dependencies, pkg_info,
                       metadata.summary, metadata_version=metadata_version)


def _parse_endist_for_egg_content(path):
    data = _parse_endist(path)
    return dict((k, data[k]) for k in data if k in ACCEPTED_ENDIST_EGG_KEYS)


def _parse_endist_for_spec_depend(path):
    data = _parse_endist(path)
    data["packages"] = _raw_packages_to_requirements(data.get("packages", []))
    return dict((k, data[k]) for k in data if k in ACCEPTED_ENDIST_SPEC_KEYS)


def _parse_endist(path):
    with open(path) as fp:
        globals_dict = {}
        local_dict = {}
        exec(fp.read(), local_dict, globals_dict)

    for k in globals_dict:
        if k in UNSUPPORTED_ENDIST_KEYS:
            msg = "key {0!r} not yet supported in {1!r}".format(k, ENDIST_DAT)
            raise NotImplementedError(msg)
    return globals_dict


def _add_files(z, dir_path, regex_string, archive_dir):
    r = re.compile(regex_string)
    archive_dir = archive_dir.strip('/')

    print("dir_path: {0!r}".format(dir_path))
    print("rx: {0!r}".format(regex_string))
    print("archive_dir: {0!r}".format(archive_dir))

    arcnames = set()

    for filename in os.listdir(dir_path):
        path = os.path.join(dir_path, filename)
        if not (r.match(filename) and os.path.isfile(path)):
            continue

        print("\tfn={0!r}".format(filename))

        arcname = archive_dir + '/' + filename
        if os.path.islink(path):
            msg = "Soft link support not yet implemented\n"
            raise NotImplementedError(msg)
        elif os.path.isfile(path):
            z.add_file_as(path, arcname)
            arcnames.add(arcname)
        else:
            raise EnstallerException("Neiher link nor file:" % path)

    return arcnames


def repack(source_egg_path, build_number=1, platform_string=None,
           python=_UNSPECIFIED, abi_tag=_UNSPECIFIED, metadata_version=None):
    metadata = _get_spec(
        source_egg_path, build_number, platform_string, python, abi_tag,
        metadata_version
    )

    parent_dir = os.path.dirname(os.path.abspath(source_egg_path))
    target_egg_path = os.path.join(parent_dir, metadata.egg_name)

    if os.path.exists(target_egg_path) and \
            samefile(source_egg_path, target_egg_path):
        msg = "source and repack-ed egg are the same file: {0!r}. Inplace " \
              "mode not yet implemented."
        raise EnstallerException(msg.format(source_egg_path))
    # XXX: implement endist.dat/app handling

    print(20 * '-' + '\n' + metadata.spec_depend_string + 20 * '-')

    with ZipFile(source_egg_path) as source:
        tempdir = tempfile.mkdtemp()
        try:
            with EggBuilder(metadata, cwd=parent_dir) as target:
                if os.path.exists(ENDIST_DAT):
                    data = _parse_endist_for_egg_content(ENDIST_DAT)
                    for entry in data.get("add_files", []):
                        _add_files(target, entry[0], entry[1], entry[2])
                files_to_skip = set(target._fp.namelist())

                for f in source.namelist():
                    if f not in files_to_skip:
                        source_path = source.extract(f, tempdir)
                        target.add_file_as(source_path, f)
        finally:
            shutil.rmtree(tempdir)


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
    p.add_argument("--abi", dest="abi_tag",
                   help="PEP425 abi tag. Will be guessed if not specified."
                        "Note: the tag format will not be validated.")
    p.add_argument("-m", "--metadata-version", dest="metadata_version",
                   default=DEFAULT_METADATA_VERSION,
                   help="Metadata version to use when generating the egg "
                        "(default: %(default)s)")
    ns = p.parse_args(argv)

    if isinstance(ns.metadata_version, string_types):
        metadata_version = MetadataVersion.from_string(ns.metadata_version)
    else:
        metadata_version = ns.metadata_version

    abi_tag = ns.abi_tag or _UNSPECIFIED
    repack(
        ns.egg, ns.build_number, ns.platform_string, abi_tag=abi_tag,
        metadata_version=metadata_version
    )


if __name__ == "__main__":  # pragma: no cover
    main()
