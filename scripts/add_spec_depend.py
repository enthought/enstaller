"""
Simple script to inject a minimal spec/depend file in an existing egg as built
from bdist_egg::

    python add_spec_depend.py enstaller-4.6.5-py27.egg

Should work for any enstaller >= 4.5.3.
"""
import optparse
import os.path
import re
import textwrap
import sys
import zipfile


R_ENSTALLER = re.compile("^enstaller-(?P<version>.+)-py(?P<python_version>.+)\.egg$")


def parse_version(p, path):
    filename = os.path.basename(path)

    m = R_ENSTALLER.match(filename)
    if m is None:
        p.error("Could not understand filename %s" % (filename,))

    d = m.groupdict()
    
    return d["version"], d["python_version"]


def write_spec_depend(egg, full_version, python_version):
    spec_depend = textwrap.dedent("""\
        metadata_version = '1.1'
        name = 'enstaller'
        version = '{0}'
        build = 1

        arch = None
        platform = None
        osdist = None
        python = '{1}'
        packages = []
    """.format(full_version, python_version))

    archive = "EGG-INFO/spec/depend"

    zp = zipfile.ZipFile(egg, "a", compression=zipfile.ZIP_DEFLATED)
    try:
        if archive in zp.namelist():
            raise ValueError("{0!r} already in egg !".format(archive))
        else:
            zp.writestr(archive, spec_depend)
    finally:
        zp.close()


def main(argv=None):
    argv = argv or sys.argv[1:]

    p = optparse.OptionParser(usage=__doc__)
    (options, args) = p.parse_args(argv)

    if len(args) != 1:
        p.error("Expects exactly one argument")

    egg = args[0]

    full_version, python_version = parse_version(p, egg)
    write_spec_depend(egg, full_version, python_version)


if __name__ == "__main__":
    main()
