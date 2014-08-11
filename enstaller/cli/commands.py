from __future__ import absolute_import, print_function

import sys
import textwrap

from enstaller.freeze import get_freeze_list
from enstaller.history import History
from enstaller.repository import Repository

from .utils import FMT, FMT4, VB_FMT, install_time_string, print_installed


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


def list_option(prefixes, pat=None):
    for prefix in reversed(prefixes):
        print("prefix:", prefix)
        repository = Repository._from_prefixes([prefix])
        print_installed(repository, pat)
        print()


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


def search(remote_repository, installed_repository, config, user, pat=None):
    """
    Print the packages that are available in the (remote) repository.

    It also prints a '*' in front of packages already installed.
    """
    # Flag indicating if the user received any 'not subscribed to'
    # messages
    subscribed = True

    print(FMT4 % ('Name', '  Versions', 'Product', 'Note'))
    print(80 * '=')

    names = {}
    for metadata in remote_repository.iter_packages():
        names[metadata.name] = metadata.name

    installed = {}
    for package in installed_repository.iter_packages():
        installed[package.name] = VB_FMT % package._compat_dict

    for name in sorted(names, key=lambda s: s.lower()):
        if pat and not pat.search(name):
            continue
        disp_name = names[name]
        installed_version = installed.get(name)
        for metadata in remote_repository.find_sorted_packages(name):
            version = metadata.full_version
            disp_ver = (('* ' if installed_version == version else '  ') +
                        version)
            available = metadata.available
            product = metadata.product
            if not available:
                subscribed = False
            print(FMT4 % (disp_name, disp_ver, product,
                  '' if available else 'not subscribed to'))
            disp_name = ''

    if config.use_webservice and not subscribed:
        msg = textwrap.dedent("""\
            Note: some of those packages are not available at your current
            subscription level ({0!r}).""".format(user.subscription_level))
        print(msg)
