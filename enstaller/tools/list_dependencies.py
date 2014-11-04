from __future__ import print_function

import argparse
import sys

import enstaller.plat

from enstaller.cli.utils import repository_factory
from enstaller.config import Configuration
from enstaller.session import Session
from enstaller.solver import Requirement
from enstaller.solver.resolve import Resolve


def query_platform(session, indices, requirement, platform):
    repository = repository_factory(session, indices)

    requirement = Requirement(requirement)
    resolve = Resolve(repository)

    def print_level(parent, level=0):
        level += 4
        for r in resolve._dependencies_from_egg(parent):
            print("{0}{1}".format(level * " ", r))
            egg = resolve._latest_egg(r)
            if egg is None:
                msg = "Error: Could not find egg for requirement {0!r}"
                print(msg.format(r))
                sys.exit(-1)
            print_level(egg, level)

    root = resolve._latest_egg(requirement)
    if root is None:
        print("No egg found for requirement {0}".format(requirement))
    else:
        print("Resolving dependencies for {0}: {1}".format(requirement, root))
        print_level(root)


def main(argv=None):
    argv = argv or sys.argv[1:]

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
        auth = config.auth
    else:
        auth = tuple(namespace.auth.split(":"))

    session = Session.from_configuration(config)
    with session:
        session.authenticate(auth)

        if namespace.platform == "all":
            platforms = ["rh5-32", "rh5-64", "osx-32", "osx-64", "win-32", "win-64"]
            for platform in platforms:
                query_platform(session, config.indices, namespace.requirement,
                               platform)
        else:
            query_platform(session, config.indices, namespace.requirement,
                           namespace.platform)


if __name__ == "__main__":  # pragma: nocover
    main()
