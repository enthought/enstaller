import argparse
import sys

import enstaller.plat

from enstaller.config import Configuration
from enstaller.store.indexed import RemoteHTTPIndexedStore
from enstaller.resolve import Req, Resolve
from enstaller.enpkg import get_writable_local_dir

URL_TEMPLATE = 'https://api.enthought.com/eggs/%s/'

def get_default_remote(config, plat):
    url = URL_TEMPLATE % plat
    local_dir = get_writable_local_dir(config)
    print "Using API URL {}".format(url)
    return RemoteHTTPIndexedStore(url, local_dir)

def query_platform(config, userpass, requirement, platform):
    remote = get_default_remote(config, platform)
    req = Req(requirement)

    print "Connecting to remote repositories..."
    remote.connect(userpass)

    resolver = Resolve(remote)

    def print_level(parent, level=0):
        level += 4
        for r in resolver.reqs_egg(parent):
            print "{}{}".format(level * " ", r)
            egg = resolver.get_egg(r)
            print_level(egg, level)

    root = resolver.get_egg(req)
    print("Resolving dependencies for {}: latest egg is {}".format(req, root))
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

    config = Configuration._get_default_config()

    if namespace.auth is None:
        userpass = config.get_auth()
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
