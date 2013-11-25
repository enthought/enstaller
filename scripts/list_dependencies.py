import argparse
import sys

import enstaller.plat

from enstaller import config
from enstaller.store.indexed import RemoteHTTPIndexedStore
from enstaller.resolve import Req, Resolve
from enstaller.enpkg import get_writable_local_dir

URL_TEMPLATE = 'https://api.enthought.com/eggs/%s/'

def get_default_remote(prefixes, plat):
    url = URL_TEMPLATE % plat
    local_dir = get_writable_local_dir(prefixes[0])
    print "Using API URL {}".format(url)
    return RemoteHTTPIndexedStore(url, local_dir)

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    userpass = config.get_auth()
    plat = enstaller.plat.custom_plat

    p = argparse.ArgumentParser()
    p.add_argument("requirement",
            help="Requirement string (e.g. 'mayavi')")
    p.add_argument("--platform",
            help="Platform to consider (default: %(default)s)",
            default=plat)

    namespace = p.parse_args(argv)

    remote = get_default_remote([sys.prefix], namespace.platform)
    req = Req(namespace.requirement)

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

if __name__ == "__main__":
    main()
