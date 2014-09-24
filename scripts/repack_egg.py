import argparse
import os
import sys

from enstaller.tools.repack import ENDIST_DAT, repack


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
