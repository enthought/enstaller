from __future__ import absolute_import, print_function

import datetime
import sys
import textwrap

from enstaller.auth import UserInfo
from enstaller.freeze import get_freeze_list
from enstaller.history import History
from enstaller.repository import Repository

from .utils import (FMT, FMT4, install_req, install_time_string,
                    name_egg, print_installed, updates_check)


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
        loc = 'sys' if packages[0].store_location == sys.prefix else 'user'
        print(FMT % (name, packages[0].full_version, loc))


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
        last_mtime = datetime.datetime.fromtimestamp(metadata.mtime)
        print(pad + 'Last modified: %s' % last_mtime)
        print(pad + 'MD5: %s' % metadata.md5)
        print(pad + 'Size: %s' % metadata.size)
        reqs = set(r for r in metadata.packages)
        print(pad + "Requirements: %s" % (', '.join(sorted(reqs)) or None))


def install_from_requirements(enpkg, config, args):
    """
    Install a set of requirements specified in the requirements file.
    """
    with open(args.requirements, "r") as fp:
        for req in fp:
            args.no_deps = True
            install_req(enpkg, config, req.rstrip(), args)


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


def search(remote_repository, installed_repository, config, session, pat=None):
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
        installed[package.name] = package.full_version

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
        user = UserInfo.from_session(session)
        msg = textwrap.dedent("""\
            Note: some of those packages are not available at your current
            subscription level ({0!r}).""".format(user.subscription_level))
        print(msg)


def update_all(enpkg, config, args):
    updates, EPD_update = updates_check(enpkg._remote_repository,
                                        enpkg._installed_repository)
    if not (updates or EPD_update):
        print("No new version of any installed package is available")
    else:
        if EPD_update:
            new_EPD_version = EPD_update[0]['update'].full_version
            print("EPD", new_EPD_version, "is available. "
                  "To update to it (with confirmation warning), "
                  "run 'enpkg epd'.")
        if updates:
            print("The following updates and their dependencies "
                  "will be installed")
            print(FMT % ('Name', 'installed', 'available'))
            print(60 * "=")
            for update in updates:
                print(FMT % (update['current'].name,
                             update['current'].full_version,
                             update['update'].full_version))
            for update in updates:
                install_req(enpkg, config, update['current'].name, args)


def whats_new(remote_repository, installed_repository):
    updates, EPD_update = updates_check(remote_repository,
                                        installed_repository)
    if not (updates or EPD_update):
        print("No new version of any installed package is available")
    else:
        if EPD_update:
            new_EPD_version = EPD_update[0]['update'].full_version
            print("EPD", new_EPD_version, "is available. "
                  "To update to it (with confirmation warning), run "
                  "'enpkg epd'.")
        if updates:
            print(FMT % ('Name', 'installed', 'available'))
            print(60 * "=")
            for update in updates:
                print(FMT % (name_egg(update['current'].key),
                             update['current'].full_version,
                             update['update'].full_version))
