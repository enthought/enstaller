from __future__ import absolute_import, print_function

import sys

from enstaller.freeze import get_freeze_list
from enstaller.history import History

from .utils import FMT, VB_FMT, install_time_string


def env_option(prefixes):
    print("Prefixes:")
    for p in prefixes:
        print('    %s%s' % (p, ['', ' (sys)'][p == sys.prefix]))


def freeze(prefixes):
    for package in get_freeze_list(prefixes):
        print(package)


def imports_option(repository):
    print(FMT % ('Name', 'Version', 'Location'))
    print(60 * "=")

    names = set(package.name for package in repository.iter_packages())
    for name in sorted(names, key=lambda s: s.lower()):
        packages = repository.find_packages(name)
        info = packages[0]._compat_dict
        loc = 'sys' if packages[0].store_location == sys.prefix else 'user'
        print(FMT % (name, VB_FMT % info, loc))


def info_option(remote_repository, installed_repository, name):
    name = name.lower()
    print('Package:', name)
    print(install_time_string(installed_repository, name))
    pad = 4*' '
    for metadata in remote_repository.find_sorted_packages(name):
        print('Version: ' + metadata.full_version)
        print(pad + 'Product: %s' % metadata.product)
        print(pad + 'Available: %s' % metadata.available)
        print(pad + 'Python version: %s' % metadata.python)
        print(pad + 'Store location: %s' % metadata.store_location)
        print(pad + 'MD5: %s' % metadata.md5)
        print(pad + 'Size: %s' % metadata.size)
        reqs = set(r for r in metadata.packages)
        print(pad + "Requirements: %s" % (', '.join(sorted(reqs)) or None))


def print_history(prefix):
    h = History(prefix)
    h.update()
    h.print_log()


def revert(enpkg, revert_arg):
    actions = enpkg.revert_actions(revert_arg)
    if actions:
        enpkg.execute(actions)
    else:
        print("Nothing to do")
