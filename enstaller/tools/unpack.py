"""
A dumb egg unpacker.

It only unpack the egg, and do *not* pre/post process them. You probably do not
want to use this tool if you are not sure about its purpose.
"""
import argparse
import os.path
import posixpath
import sys

from egginst.main import EGG_INFO
from egginst._zipfile import ZipFile


def extract_egg(path, to):
    usr = posixpath.join(EGG_INFO, "usr")

    with ZipFile(path) as zp:
        for p in zp.infolist():
            if p.filename.startswith(usr):
                target = os.path.relpath(p.filename, usr)
                zp.extract_to(p, target, to)


def main(argv=None):
    argv = argv or sys.argv[1:]

    p = argparse.ArgumentParser("A dumb egg unpacker")
    p.add_argument("target",
                   help="Directory where to extract the egg.")
    p.add_argument("eggs", help="Path to the egg.", nargs="+")

    ns = p.parse_args(argv)

    for egg in ns.eggs:
        extract_egg(egg, ns.target)


if __name__ == "__main__":  # pragma: nocover
    main()
