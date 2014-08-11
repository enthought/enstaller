from __future__ import absolute_import, print_function

import sys

from .utils import FMT, VB_FMT


def env_option(prefixes):
    print("Prefixes:")
    for p in prefixes:
        print('    %s%s' % (p, ['', ' (sys)'][p == sys.prefix]))


def imports_option(repository):
    print(FMT % ('Name', 'Version', 'Location'))
    print(60 * "=")

    names = set(package.name for package in repository.iter_packages())
    for name in sorted(names, key=lambda s: s.lower()):
        packages = repository.find_packages(name)
        info = packages[0]._compat_dict
        loc = 'sys' if packages[0].store_location == sys.prefix else 'user'
        print(FMT % (name, VB_FMT % info, loc))
