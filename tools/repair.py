import argparse
import os.path
import sys

from egginst._repair_broken_egg_info import repair


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    p = argparse.ArgumentParser(description="Script to repair .egg-info directories.")
    p.add_argument("-n", "--dry-run", help="Do not modify anything", action="store_true")
    p.add_argument("--prefix", help="The prefix to fix", default=sys.prefix)
    ns = p.parse_args(argv)

    prefix = ns.prefix
    if not os.path.exists(prefix):
        p.error("Prefix {0} does not exist".format(prefix))

    repair(prefix, ns.dry_run)


if __name__ == "__main__":
    main()
