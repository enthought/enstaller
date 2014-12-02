import argparse
import sys

from .commands import install, remove, update_all


def handle_args(argv):
    p = argparse.ArgumentParser()
    subparsers = p.add_subparsers(help='sub-command help')

    install_p = subparsers.add_parser("install")
    install_p.set_defaults(func=install)

    remove_p = subparsers.add_parser("remove")
    remove_p.set_defaults(func=remove)

    update_all_p = subparsers.add_parser("update_all")
    update_all_p.set_defaults(func=update_all)

    return p.parse_args(argv)


def main(argv=None):
    argv = argv or sys.argv[1:]

    namespace = handle_args(argv)
    namespace.func()

    sys.exit(0)


if __name__ == "__main__":
    main()
