# Author: Ilan Schnell <ischnell@enthought.com>
"""\
The enstaller package is a tool for managing egginst-based installs.
Its primary command-line interface program is enpkg, which processes user
commands and in turn invokes egginst to do the actual installations.
enpkg can access eggs from both local and HTTP repositories.
"""
from __future__ import print_function

import argparse
import datetime
import errno
import io
import json
import logging
import ntpath
import os
import posixpath
import re
import site
import string
import sys
import textwrap
import urlparse
import warnings

from argparse import ArgumentParser
from os.path import isfile

from egginst.progress import console_progress_manager_factory, dummy_progress_bar_factory
from enstaller._version import is_released as IS_RELEASED

import enstaller

from enstaller.auth import authenticate
from enstaller.errors import (EnpkgError, InvalidPythonPathConfiguration,
                              InvalidConfiguration, InvalidFormat,
                              NoPackageFound, UnavailablePackage, EXIT_ABORTED)
from enstaller.config import (ENSTALLER4RC_FILENAME, HOME_ENSTALLER4RC,
                              SYS_PREFIX_ENSTALLER4RC, Configuration, add_url,
                              configuration_read_search_order,
                              convert_auth_if_required, input_auth,
                              print_config, write_default_config)
from enstaller.egg_meta import split_eggname
from enstaller.errors import AuthFailedError
from enstaller.enpkg import Enpkg, ProgressBarContext
from enstaller.fetch import DownloadManager, URLFetcher
from enstaller.freeze import get_freeze_list
from enstaller.history import History
from enstaller.legacy_stores import parse_index
from enstaller.repository import Repository, egg_name_to_name_version
from enstaller.requests_utils import _ResponseIterator
from enstaller.resolve import Req, comparable_info
from enstaller.solver import Solver, create_enstaller_update_repository
from enstaller.utils import abs_expanduser, exit_if_sudo_on_venv, prompt_yes_no


logger = logging.getLogger(__name__)


FMT = '%-20s %-20s %s'
VB_FMT = '%(version)s-%(build)s'
FMT4 = '%-20s %-20s %-20s %s'

PLEASE_AUTH_MESSAGE = ("No authentication configured, required to continue.\n"
                       "To login, type 'enpkg --userpass'.")

DEFAULT_TEXT_WIDTH = 79


def env_option(prefixes):
    print("Prefixes:")
    for p in prefixes:
        print('    %s%s' % (p, ['', ' (sys)'][p == sys.prefix]))


def disp_store_info(info):
    sl = info.get('store_location')
    if not sl:
        return '-'
    for rm in 'http://', 'https://', 'www', '.enthought.com', '/repo/':
        sl = sl.replace(rm, '')
    return sl.replace('/eggs/', ' ').strip('/')


def name_egg(egg):
    return split_eggname(egg)[0]


def install_time_string(installed_repository, name):
    lines = []
    for info in installed_repository.find_packages(name):
        lines.append('%s was installed on: %s' % (info.key, info.ctime))
    return "\n".join(lines)


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


def print_installed(repository, pat=None):
    print(FMT % ('Name', 'Version', 'Store'))
    print(60 * '=')
    for package in repository.iter_packages():
        if pat and not pat.search(package.name):
            continue
        info = package._compat_dict
        print(FMT % (name_egg(package.key), VB_FMT % info, disp_store_info(info)))


def list_option(prefixes, pat=None):
    for prefix in reversed(prefixes):
        print("prefix:", prefix)
        repository = Repository._from_prefixes([prefix])
        print_installed(repository, pat)
        print()


def imports_option(repository):
    print(FMT % ('Name', 'Version', 'Location'))
    print(60 * "=")

    names = set(package.name for package in repository.iter_packages())
    for name in sorted(names, key=string.lower):
        packages = repository.find_packages(name)
        info = packages[0]._compat_dict
        loc = 'sys' if packages[0].store_location == sys.prefix else 'user'
        print(FMT % (name, VB_FMT % info, loc))


def search(enpkg, remote_repository, installed_repository, config, user,
           pat=None):
    """
    Print the packages that are available in the (remote) KVS.
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

    for name in sorted(names, key=string.lower):
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


def updates_check(remote_repository, installed_repository):
    updates = []
    EPD_update = []
    for package in installed_repository.iter_packages():
        key = package.key
        info = package._compat_dict

        info["key"] = key
        av_metadatas = remote_repository.find_sorted_packages(info['name'])
        if len(av_metadatas) == 0:
            continue
        av_metadata = av_metadatas[-1]
        if av_metadata.comparable_version > comparable_info(info):
            if info['name'] == "epd":
                EPD_update.append({'current': info, 'update': av_metadata})
            else:
                updates.append({'current': info, 'update': av_metadata})
    return updates, EPD_update


def whats_new(remote_repository, installed_repository):
    updates, EPD_update = updates_check(remote_repository, installed_repository)
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
                print(FMT % (name_egg(update['current']['key']),
                             VB_FMT % update['current'],
                             update['update'].full_version))


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
            print ("The following updates and their dependencies "
                   "will be installed")
            print(FMT % ('Name', 'installed', 'available'))
            print(60 * "=")
            for update in updates:
                print(FMT % (name_egg(update['current']['key']),
                             VB_FMT % update['current'],
                             update['update'].full_version))
            for update in updates:
                install_req(enpkg, config, update['current']['name'], args)

def epd_install_confirm(force_yes=False):
    print("Warning: 'enpkg epd' will downgrade any packages that are currently")
    print("at a higher version than in the specified EPD release.")
    print("Usually it is preferable to update all installed packages with:")
    print("    enpkg --update-all")
    return prompt_yes_no("Are you sure that you wish to proceed? (y/[n]) ",
                         force_yes)

def install_req(enpkg, config, req, opts):
    """
    Try to execute the install actions.
    """
    # Unix exit-status codes
    FAILURE = 1
    req = Req.from_anything(req)

    def _done(exit_status):
        sys.exit(exit_status)

    def _get_unsupported_packages(actions):
        ret = []
        for opcode, egg in actions:
            if opcode == "install":
                name, version = egg_name_to_name_version(egg)
                package = enpkg._remote_repository.find_package(name, version)
                if package.product == "pypi":
                    ret.append(package)
        return ret

    def _ask_pypi_confirmation(actions):
        unsupported_packages = _get_unsupported_packages(actions)
        if len(unsupported_packages) > 0:
            package_list = sorted("'{0}-{1}'".format(p.name, p.full_version)
                                  for p in unsupported_packages)
            package_list_string = "\n".join(package_list)

            msg = textwrap.dedent("""\
            The following packages are coming from the PyPi repo:

            {0}

            The PyPi repository which contains >10,000 untested ("as is")
            packages. Some packages are licensed under GPL or other licenses
            which are prohibited for some users. Dependencies may not be
            provided. If you need an updated version or if the installation
            fails due to unmet dependencies, the Knowledge Base article
            Installing external packages into Canopy Python
            (https://support.enthought.com/entries/23389761) may help you with
            installing it.
            """.format(package_list_string))
            print(msg)

            msg = "Are you sure that you wish to proceed?  (y/[n]) "
            if not prompt_yes_no(msg, opts.yes):
                sys.exit(0)

    try:
        mode = 'root' if opts.no_deps else 'recur'
        actions = enpkg._solver.install_actions(
                req,
                mode=mode,
                force=opts.force, forceall=opts.forceall)
        _ask_pypi_confirmation(actions)
        enpkg.execute(actions)
        if len(actions) == 0:
            print("No update necessary, %r is up-to-date." % req.name)
            print(install_time_string(enpkg._installed_repository,
                                      req.name))
    except UnavailablePackage as e:
        username, __ = config.auth
        user_info = authenticate(config)
        subscription = user_info.subscription_level
        msg = textwrap.dedent("""\
            Cannot install {0!r}, as this package (or some of its requirements)
            are not available at your subscription level {1!r} (You are
            currently logged in as {2!r}).
            """.format(str(e.requirement), subscription, username))
        print()
        print(textwrap.fill(msg, DEFAULT_TEXT_WIDTH))
        _done(FAILURE)
    except NoPackageFound as e:
        print(str(e))
        _done(FAILURE)
    except OSError as e:
        if e.errno == errno.EACCES and sys.platform == 'darwin':
            print("Install failed. OSX install requires admin privileges.")
            print("You should add 'sudo ' before the 'enpkg' command.")
            _done(FAILURE)
        else:
            raise


def update_enstaller(enpkg, config, autoupdate, opts):
    """
    Check if Enstaller is up to date, and if not, ask the user if he
    wants to update.  Return boolean indicating whether enstaller was
    updated.
    """
    updated = False
    if not autoupdate:
        return updated
    if not IS_RELEASED:
        return updated
    new_repository = create_enstaller_update_repository(
        enpkg._remote_repository, enstaller.__version__)
    solver = Solver(new_repository, enpkg._top_installed_repository)
    if len(solver._install_actions_enstaller()) > 0:
        if prompt_yes_no("Enstaller is out of date.  Update? ([y]/n) ",
                         opts.yes):
            install_req(enpkg, config, 'enstaller', opts)
            updated = True
    return updated

def get_package_path(prefix):
    """Return site-packages path for the given repo prefix.

    Note: on windows the path is lowercased and returned.
    """
    if sys.platform == 'win32':
        return ntpath.join(prefix, 'Lib', 'site-packages').lower()
    else:
        postfix = 'lib/python{0}.{1}/site-packages'.format(*sys.version_info)
        return posixpath.join(prefix, postfix)


def check_prefixes(prefixes):
    """
    Check that package prefixes lead to site-packages that are on the python
    path and that the order of the prefixes matches the python path.
    """
    index_order = []
    if sys.platform == 'win32':
        sys_path = [x.lower() for x in sys.path]
    else:
        sys_path = sys.path
    for prefix in prefixes:
        path = get_package_path(prefix)
        try:
            index_order.append(sys_path.index(path))
        except ValueError:
            raise InvalidPythonPathConfiguration("Expected to find %s in PYTHONPATH" % (path,))
    else:
        if not index_order == sorted(index_order):
            raise InvalidPythonPathConfiguration("Order of path prefixes doesn't match PYTHONPATH")


def needs_to_downgrade_enstaller(reqs):
    """
    Returns True if the running enstaller would be downgraded by satisfying the
    list of requirements.
    """
    for req in reqs:
        if req.name == "enstaller" and req.version is not None:
            return True
    return False


def get_config_filename(use_sys_config):
    if use_sys_config:                           # --sys-config
        config_filename = SYS_PREFIX_ENSTALLER4RC
    else:
        paths = [os.path.join(d, ENSTALLER4RC_FILENAME) for d in
                 configuration_read_search_order()]
        for path in paths:
            if isfile(path):
                config_filename = path
                break
        else:
            config_filename = HOME_ENSTALLER4RC

    return config_filename


def _invalid_authentication_message(auth_url, username, original_error_string):
    if "routines:SSL3_GET_SERVER_CERTIFICATE:certificate verify failed" \
            in original_error_string:
        paragraph1 = textwrap.fill(textwrap.dedent("""\
            Could not authenticate against {0!r} because the underlying SSL
            library used by enpkg could not verify the CA certificate. This
            could happen because you have a very old SSL library. You can disable
            CA certificate checking by using the -k/--insecure option of enpkg::
            """.format(auth_url)))
        template = paragraph1 + textwrap.dedent("""

                enpkg -k <your options>

            The original error is:

            {{0}}
            """.format(auth_url))
        formatted_error = "\n".join(" "* 4 + line for line in \
                                    textwrap.wrap("`" +
                                                  original_error_string + "`"))
        msg = template.format(formatted_error)
        auth_error = False
    else:
        msg = textwrap.dedent("""\
            Could not authenticate with user '{0}' against {1!r}. Please check
            your credentials/configuration and try again (original error is:
            {2!r}).
            """.format(username, auth_url, original_error_string))
        auth_error = True
    return msg, auth_error


def ensure_authenticated_config(config, config_filename, verify=True):
    try:
        user = authenticate(config, verify=verify)
    except AuthFailedError as e:
        username, _ = config.auth
        msg, is_auth_error = _invalid_authentication_message(config.store_url,
                                                             username, str(e))
        print(msg)
        if is_auth_error:
            print("\nYou can change your authentication details with "
                  "'enpkg --userpass'.")
        sys.exit(-1)
    else:
        convert_auth_if_required(config_filename)
        return user


def _display_store_name(store_location):
    parts = urlparse.urlsplit(store_location)
    return urlparse.urlunsplit(("", "", parts[2], parts[3], parts[4]))

def _fetch_json_with_progress(resp, store_location, quiet=False):
    data = io.BytesIO()

    length = int(resp.headers.get("content-length", 0))
    display = _display_store_name(store_location)

    if quiet:
        progress = dummy_progress_bar_factory()
    else:
        progress = console_progress_manager_factory("Fetching index", display,
                                                    size=length)
    with progress:
        for chunk in _ResponseIterator(resp):
            data.write(chunk)
            progress.update(len(chunk))

    return json.loads(data.getvalue().decode("utf-8"))


def repository_factory(fetcher, config, quiet=False):
    repository = Repository()
    for url, store_location in config.indices:
        resp = fetcher.fetch(url)
        resp.raise_for_status()

        for package in parse_index(_fetch_json_with_progress(resp,
                                                             store_location,
                                                             quiet),
                                   store_location):
            repository.add_package(package)
    return repository


def install_from_requirements(enpkg, config, args):
    """
    Install a set of requirements specified in the requirements file.
    """
    with open(args.requirements, "r") as fp:
        for req in fp:
            args.no_deps = True
            install_req(enpkg, config, req.rstrip(), args)


def configure_authentication_or_exit(config, config_filename, verify=True):
    n_trials = 3
    for i in range(n_trials):
        username, password = input_auth()
        if username:
            break
        else:
            print("Please enter a non empty username ({0} trial(s) left, Ctrl+C to exit)". \
                  format(n_trials - i - 1))
    else:
        print("No valid username entered (no modification was written).")
        sys.exit(-1)

    config.set_auth(username, password)
    try:
        config._checked_change_auth(config_filename, verify)
    except AuthFailedError as e:
        msg, _ = _invalid_authentication_message(config.store_url, username,
                                                 str(e))
        print(msg)
        print("\nNo modification was written.")
        sys.exit(-1)

def main(argv=None):
    if argv is None: # pragma: no cover
        argv = sys.argv[1:]

    user_base = getattr(site, "USER_BASE", abs_expanduser('~/.local'))

    p = ArgumentParser(description=__doc__)
    p.add_argument('cnames', metavar='NAME', nargs='*',
                   help='package(s) to work on')
    p.add_argument("--add-url", metavar='URL',
                   help="add a repository URL to the configuration file")
    p.add_argument("--insecure", "-k", action="store_true",
                   help="Disable SSL cert verification")
    p.add_argument("--config", action="store_true",
                   help="display the configuration and exit")
    p.add_argument('-f', "--force", action="store_true",
                   help="force install the main package "
                        "(not its dependencies, see --forceall)")
    p.add_argument("--forceall", action="store_true",
                   help="force install of all packages "
                        "(i.e. including dependencies)")
    p.add_argument("--freeze", help=argparse.SUPPRESS, action="store_true")
    p.add_argument("--imports", action="store_true",
                   help="show which packages can be imported")
    p.add_argument('-i', "--info", action="store_true",
                   help="show information about a package")
    p.add_argument("--log", action="store_true", help="print revision log")
    p.add_argument('-l', "--list", action="store_true",
                   help="list the packages currently installed on the system")
    p.add_argument('-n', "--dry-run", action="store_true",
               help="show what would have been downloaded/removed/installed")
    p.add_argument('-N', "--no-deps", action="store_true",
                   help="neither download nor install dependencies")
    p.add_argument("--env", action="store_true",
                   help="based on the configuration, display how to set "
                        "environment variables")
    p.add_argument("--prefix", metavar='PATH',
                   help="install prefix (disregarding any settings in "
                        "the config file)")
    p.add_argument("--proxy", metavar='PROXYSTR',
                   help="use a proxy for downloads."
                        " <proxy protocol>://[<proxy username>"
                        "[:<proxy password>@]]<proxy server>:<proxy port>")
    p.add_argument("--remove", action="store_true", help="remove a package")
    p.add_argument("--remove-enstaller", action="store_true",
                   help="remove enstaller (will break enpkg)")
    p.add_argument("--requirements", help=argparse.SUPPRESS)
    p.add_argument("--revert", metavar="REV#",
                   help="revert to a previous set of packages (does not revert "
                   "enstaller itself)")
    p.add_argument('-q', "--quiet", action="store_true",
                   help="Quiet output.")
    p.add_argument('-s', "--search", action="store_true",
                   help="search the online repo index "
                        "and display versions available")
    p.add_argument("--sys-config", action="store_true",
                   help="use <sys.prefix>/.enstaller4rc (even when "
                        "~/.enstaller4rc exists)")
    p.add_argument("--sys-prefix", action="store_true",
                   help="use sys.prefix as the install prefix")
    p.add_argument("--update-all", action="store_true",
                   help="update all installed packages")
    p.add_argument("--user", action="store_true",
               help="install into user prefix, i.e. --prefix=%r" % user_base)
    p.add_argument("--userpass", action="store_true",
                   help="prompt for Enthought authentication, and save in "
                   "configuration file .enstaller4rc")
    p.add_argument('-v', "--verbose", action="count", default=0,
                   help="Verbose output if specified once, very verbose if " \
                        "specified twice.")
    p.add_argument('--version', action="version",
                   version='enstaller version: ' + enstaller.__version__)
    p.add_argument("--whats-new", action="store_true",
                   help="display available updates for installed packages")
    p.add_argument("-y", "--yes", action="store_true",
                   help="Assume 'yes' to all queries and do not prompt.")

    args = p.parse_args(argv)

    config_filename = get_config_filename(args.sys_config)
    if not os.path.isfile(config_filename):
        write_default_config(config_filename)

    try:
        config = Configuration.from_file(config_filename)
    except InvalidConfiguration as e:
        print(str(e))
        sys.exit(EXIT_ABORTED)


    # Check for incompatible actions and options
    # Action options which take no package name pattern:
    simple_standalone_actions = (args.config, args.env, args.userpass,
                                args.revert, args.log, args.whats_new,
                                args.update_all, args.remove_enstaller,
                                args.add_url, args.freeze, args.requirements)
    # Action options which can take a package name pattern:
    complex_standalone_actions = (args.list, args.imports,
                                 args.search, args.info, args.remove)

    count_simple_actions = sum(bool(opt) for opt in simple_standalone_actions)
    count_complex_actions = sum(bool(opt) for opt in complex_standalone_actions)

    if count_simple_actions + count_complex_actions > 1:
        p.error('Multiple action options specified')
    if count_simple_actions > 0 and len(args.cnames) > 0:
        p.error("Option takes no arguments")

    if args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARN
    logging.basicConfig(level=level, format="%(message)s")

    if args.user:
        args.prefix = user_base

    if args.prefix and args.sys_prefix:
        p.error("Options --prefix and --sys-prefix exclude each other")

    if args.force and args.forceall:
        p.error("Options --force and --forceall exclude each other")

    pat = None
    if (args.list or args.search) and args.cnames:
        pat = re.compile(args.cnames[0], re.I)

    # make prefix
    if args.sys_prefix:
        prefix = sys.prefix
    elif args.prefix:
        prefix = args.prefix
    else:
        prefix = config.prefix

    # now make prefixes
    if prefix == sys.prefix:
        prefixes = [sys.prefix]
    else:
        prefixes = [prefix, sys.prefix]

    if args.user:
        try:
            check_prefixes(prefixes)
        except InvalidPythonPathConfiguration:
            warnings.warn("Using the --user option, but your PYTHONPATH is not setup " \
                          "accordingly")

    exit_if_sudo_on_venv(prefix)

    logger.info("prefixes")
    for prefix in prefixes:
        logger.info('    %s%s', prefix, ['', ' (sys)'][prefix == sys.prefix])

    if args.env:                                  # --env
        env_option(prefixes)
        return

    if args.log:                                  # --log
        h = History(prefix)
        h.update()
        h.print_log()
        return

    if args.freeze:
        for package in get_freeze_list(prefixes):
            print(package)
        return

    if args.list:                                 # --list
        list_option(prefixes, pat)
        return

    if args.proxy:                                # --proxy
        try:
            config.set_proxy_from_string(args.proxy)
        except InvalidConfiguration as e:
            print("Error: invalid proxy setting {0!r}".format(e))
            sys.exit(1)

    if args.config:                               # --config
        print_config(config, prefixes[0])
        return

    if args.add_url:                              # --add-url
        add_url(config_filename, config, args.add_url)
        return

    verify = not args.insecure
    if args.userpass:                             # --userpass
        configure_authentication_or_exit(config, config_filename, verify)
        return

    if not config.is_auth_configured:
        configure_authentication_or_exit(config, config_filename, verify)

    user = ensure_authenticated_config(config, config_filename, verify)

    index_fetcher = URLFetcher(config.repository_cache, config.auth,
                               config.proxy_dict, verify)
    index_fetcher._enable_etag_support()
    repository = repository_factory(index_fetcher, config, args.quiet)

    fetcher = URLFetcher(config.repository_cache, config.auth,
                         config.proxy_dict, verify)
    downloader = DownloadManager(fetcher, repository)

    if args.quiet:
        progress_bar_context = None
    else:
        progress_factory = console_progress_manager_factory
        progress_bar_context = ProgressBarContext(progress_factory)
    enpkg = Enpkg(repository, downloader, prefixes, progress_bar_context)

    if args.dry_run:
        def print_actions(actions):
            for item in actions:
                print('%-8s %s' % item)
        enpkg.execute = print_actions

    if args.imports:                              # --imports
        repository = Repository._from_prefixes(enpkg.prefixes)
        imports_option(repository)
        return

    if args.revert:                               # --revert
        actions = enpkg.revert_actions(args.revert)
        if actions:
            enpkg.execute(actions)
        else:
            print("Nothing to do")
        return

    # Try to auto-update enstaller
    if update_enstaller(enpkg, config, config.autoupdate, args):
        print("Enstaller has been updated.\n"
              "Please re-run your previous command.")
        return

    if args.search:                               # --search
        search(enpkg, enpkg._remote_repository, enpkg._installed_repository,
               config, user, pat)
        return

    if args.info:                                 # --info
        if len(args.cnames) != 1:
            p.error("Option requires one argument (name of package)")
        info_option(enpkg._remote_repository, enpkg._installed_repository,
                    args.cnames[0])
        return

    if args.whats_new:                            # --whats-new
        whats_new(enpkg._remote_repository, enpkg._installed_repository)
        return

    if args.update_all:                           # --update-all
        update_all(enpkg, config, args)
        return

    if args.requirements:
        install_from_requirements(enpkg, config, args)
        return

    if len(args.cnames) == 0 and not args.remove_enstaller:
        p.error("Requirement(s) missing")
    elif len(args.cnames) == 2:
        pat = re.compile(r'\d+\.\d+')
        if pat.match(args.cnames[1]):
            args.cnames = ['-'.join(args.cnames)]

    reqs = []
    for arg in args.cnames:
        if '-' in arg:
            name, version = arg.split('-', 1)
            reqs.append(Req(name + ' ' + version))
        else:
            reqs.append(Req(arg))

    # This code assumes we have already upgraded enstaller if needed
    if needs_to_downgrade_enstaller(reqs):
        warnings.warn("Enstaller in requirement list: enstaller will be downgraded !")
    else:
        logger.debug("Enstaller is up to date, not updating")
        reqs = [req for req in reqs if req.name != "enstaller"]

    logger.info("Requirements:")
    for req in reqs:
        logger.info('    %r', req)

    logger.info("prefix: %r", prefix)

    REMOVE_ENSTALLER_WARNING = ("Removing enstaller package will break enpkg "
                                "and is not recommended.")
    if args.remove:
        if any(req.name == 'enstaller' for req in reqs):
            print(REMOVE_ENSTALLER_WARNING)
            print("If you are sure you wish to remove enstaller, use:")
            print("    enpkg --remove-enstaller")
            return

    if args.remove_enstaller:
        print(REMOVE_ENSTALLER_WARNING)
        if prompt_yes_no("Really remove enstaller? (y/[n]) ", args.yes):
            args.remove = True
            reqs = [Req('enstaller')]

    if any(req.name == 'epd' for req in reqs):
        if args.remove:
            p.error("Can't remove 'epd'")
        elif len(reqs) > 1:
            p.error("Can't combine 'enpkg epd' with other packages.")
        elif not epd_install_confirm(args.yes):
            return

    for req in reqs:
        if args.remove:                               # --remove
            try:
                enpkg.execute(enpkg._solver.remove_actions(req))
            except EnpkgError as e:
                print(e.message)
        else:
            install_req(enpkg, config, req, args)

def main_noexc(argv=None):
    if "ENSTALLER_DEBUG" in os.environ:
        enstaller_debug = True
    else:
        enstaller_debug = False

    try:
        main(argv)
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(EXIT_ABORTED)
    except Exception as e:
        msg = """\
%s: Error: %s crashed (uncaught exception %s: %s).
Please report this on enstaller issue tracker:
    http://github.com/enthought/enstaller/issues"""
        if enstaller_debug:
            raise
        else:
            msg += "\nYou can get a full traceback by setting the ENSTALLER_DEBUG environment variable"
            print(msg % ("enstaller", "enstaller", e.__class__, repr(e)))
            sys.exit(1)

if __name__ == '__main__': # pragma: no cover
    main_noexc()
