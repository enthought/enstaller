import argparse
import json
import sys

import requests

import enstaller.config
import enstaller.plat

URL_TEMPLATE = 'https://api.enthought.com/eggs/%s/'
#URL_TEMPLATE = 'https://staging.enthought.com/eggs/%s/'

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    plat = enstaller.plat.custom_plat

    p = argparse.ArgumentParser()
    p.add_argument("--url",
                  help="url template (default: %(default)s).",
                  default=URL_TEMPLATE)
    p.add_argument("--platform",
                  help="Platform to consider (default: %(default)s).",
                  default=plat)
    p.add_argument("--auth",
                  help="Authentification.",
                  default=None)
    p.add_argument("--pypi", action="store_true",
                  help="If given, download the index containing pypi (no pypi by default).",
                  default=False)
    namespace = p.parse_args(argv)

    platform = namespace.platform
    auth = namespace.auth
    if auth is None:
        auth = enstaller.config.get_auth()
    else:
        auth = tuple(auth.split(":"))

    url = namespace.url % platform

    print "Using user {}".format(auth[0])
    url += "index.json"
    if namespace.pypi:
        url += "?pypi=true"

    res = requests.get(url, auth=auth)
    with open("index-{}.json".format(platform), "wt") as fp:
        fp.write(json.dumps(res.json(), sort_keys=True, indent=4,
                            separators=(',', ': ')))

if __name__ == "__main__":
    main()
