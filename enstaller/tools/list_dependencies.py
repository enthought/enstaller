from __future__ import print_function

import argparse
import sys

import enstaller.plat

from enstaller.cli.utils import repository_factory
from enstaller.config import Configuration
from enstaller.session import Session
from enstaller.solver.legacy_requirement import _LegacyRequirement
from enstaller.solver.resolve import Resolve


def query_platform(session, repository_infos, requirement, platform):
    repository = repository_factory(session, repository_infos)

    requirement = _LegacyRequirement.from_requirement_string(requirement)
    resolve = Resolve(repository)

    def print_level(parent, level=0):
        level += 4
        for r in resolve._dependencies_from_package(parent):
            print("{0}{1}".format(level * " ", r))
            package = resolve._latest_package(r)
            if package is None:
                msg = "Error: Could not find package for requirement {0!r}"
                print(msg.format(r))
                sys.exit(-1)
            print_level(package, level)

    root = resolve._latest_package(requirement)
    if root is None:
        print("No egg found for requirement {0}".format(requirement))
    else:
        print("Resolving dependencies for {0}: {1}".format(
            requirement, root.key
        ))
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
                query_platform(session, config.repositories,
                               namespace.requirement, platform)
        else:
            query_platform(session, config.repositories, namespace.requirement,
                           namespace.platform)


if __name__ == "__main__":  # pragma: nocover
    main()
