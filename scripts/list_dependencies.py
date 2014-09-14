import argparse
import sys

import enstaller.plat

from enstaller.config import Configuration
from enstaller.main import repository_factory
from enstaller.solver import Requirement
from enstaller.solver.resolve import Resolve


def query_platform(config, userpass, requirement, platform):
    repository = repository_factory(config)

    requirement = Requirement(requirement)
    resolve = Resolve(repository)

    def print_level(parent, level=0):
        level += 4
        for r in resolve._dependencies_from_egg(parent):
            print "{0}{1}".format(level * " ", r)
            egg = resolve._latest_egg(r)
            print_level(egg, level)

    root = resolve._latest_egg(requirement)
    print("Resolving dependencies for {0}: {1}".format(requirement, root))
    print_level(root)

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    plat = enstaller.plat.custom_plat

    p = argparse.ArgumentParser()
    p.add_argument("requirement",
            help="Requirement string (e.g. 'mayavi')")
    p.add_argument("--platform",
            help="Platform to consider (default: %(default)s). 'all' works as well",
            default=plat)
    p.add_argument("--auth",
            help="Authentication (default: enpkg credentials)")

    namespace = p.parse_args(argv)

    config = Configuration._from_legacy_locations()
    config._platform = namespace.platform

    if namespace.auth is None:
        userpass = config.auth
    else:
        userpass = tuple(namespace.auth.split(":"))

    if namespace.platform == "all":
        platforms = ["rh5-32", "rh5-64", "osx-32", "osx-64", "win-32", "win-64"]
        for platform in platforms:
            query_platform(config, userpass, namespace.requirement, platform)
    else:
        query_platform(config, userpass, namespace.requirement, namespace.platform)

if __name__ == "__main__":
    main()
