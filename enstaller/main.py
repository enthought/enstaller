# Author: Ilan Schnell <ischnell@enthought.com>
"""\
The enstaller package is a tool for managing egginst-based installs.
Its primary command-line interface program is enpkg, which processes user
commands and in turn invokes egginst to do the actual installations.
enpkg can access eggs from both local and HTTP repositories.
"""
from __future__ import print_function

import argparse
import logging
import ntpath
import os
import posixpath
import re
import site
import sys
import textwrap
import warnings

from argparse import ArgumentParser
from os.path import isfile

from egginst.main import EGG_INFO
from egginst.progress import console_progress_manager_factory
from egginst.vendor.six.moves import http_client

import enstaller

from enstaller.auth import UserPasswordAuth
from enstaller.errors import (EnpkgError, EnstallerException,
                              InvalidPythonPathConfiguration,
                              InvalidConfiguration,
                              EXIT_ABORTED)
from enstaller.config import (ENSTALLER4RC_FILENAME, HOME_ENSTALLER4RC,
                              Configuration, add_url,
                              configuration_read_search_order,
                              convert_auth_if_required,
                              print_config, write_default_config)
from enstaller.session import Session
from enstaller.errors import AuthFailedError, NoSuchPackage
from enstaller.enpkg import Enpkg, ProgressBarContext
from enstaller.repository import InstalledPackageMetadata, Repository
from enstaller.solver import Request, Requirement
from enstaller.utils import abs_expanduser, input_auth, prompt_yes_no
from enstaller.vendor import requests
from enstaller.versions.enpkg import EnpkgVersion

from enstaller.cli.commands import (env_option, freeze, imports_option,
                                    info_option, install_from_requirements,
                                    list_option, print_history, revert, search,
                                    update_all, whats_new)
from enstaller.cli.utils import (exit_if_root_on_non_owned,
                                 humanize_ssl_error_and_die, install_req,
                                 repository_factory)

from enstaller._update_support import inplace_update

logger = logging.getLogger(__name__)

PLEASE_AUTH_MESSAGE = ("No authentication configured, required to continue.\n"
                       "To login, type 'enpkg --userpass'.")


def epd_install_confirm(force_yes=False):
    msg = textwrap.dedent("""\
        Warning: 'enpkg epd' will downgrade any packages that are currently")
        at a higher version than in the specified EPD release.
        Usually it is preferable to update all installed packages with:
            enpkg --update-all""")
    print(msg)
    return prompt_yes_no("Are you sure that you wish to proceed? (y/[n]) ",
                         force_yes)


def _get_enstaller_comparable_version(prefix, package_name):
    runtime_version = \
        EnpkgVersion.from_upstream_and_build(enstaller.__version__, 1)

    egg_info_dir = os.path.join(prefix, EGG_INFO, package_name)
    try:
        # Installed as an egg in sys.prefix
        enstaller_package = \
            InstalledPackageMetadata.from_meta_dir(egg_info_dir)
        if str(enstaller_package.version.upstream) != enstaller.__version__:
            # It is both installed as an egg and from sources/develop mode, the
            # latter takes precedence
            current_comparable_version = runtime_version
        else:
            current_comparable_version = enstaller_package.version
    except EnstallerException:
        # Installed from sources, no build number
        current_comparable_version = runtime_version

    return current_comparable_version


def update_enstaller(session, repository, opts):
    """
    Check if Enstaller is up to date, and if not, ask the user if he
    wants to update.  Return boolean indicating whether enstaller was
    updated.
    """
    updated = False
    if not enstaller.__is_released__:
        return updated

    package_name = "enstaller"

    current_comparable_version = \
        _get_enstaller_comparable_version(sys.prefix, package_name)

    try:
        latest = repository.find_latest_package(package_name)
    except NoSuchPackage:
        updated = False
    else:
        if latest.version > current_comparable_version:
            if prompt_yes_no("Enstaller is out of date.  Update? ([y]/n) ",
                             opts.yes):
                inplace_update(session, repository, latest)
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
            msg = "Expected to find %s in PYTHONPATH" % (path, )
            raise InvalidPythonPathConfiguration(msg)
    else:
        if not index_order == sorted(index_order):
            msg = "Order of path prefixes doesn't match PYTHONPATH"
            raise InvalidPythonPathConfiguration(msg)


def needs_to_downgrade_enstaller(reqs):
    """
    Returns True if the running enstaller would be downgraded by satisfying the
    list of requirements.
    """
    for req in reqs:
        if req.name == "enstaller" and req.version is not None:
            return True
    return False


def _get_config_candidate():
    """ Return a full path if one candidate is found, None if no config file
    was found.
    """
    paths = [os.path.join(d, ENSTALLER4RC_FILENAME) for d in
             configuration_read_search_order()]
    for path in paths:
        if isfile(path):
            return path


def _invalid_authentication_message(auth, exc):
    assert isinstance(exc, AuthFailedError)

    if exc.original_exception is None:
        original_error = str(exc)
    else:
        original_error = str(exc.original_exception)

    header = auth.cant_login_message
    msg = textwrap.dedent("""\
        {0}
        Please check your credentials/configuration and try again
        (original error is: {1!r}).
        """.format(header, str(original_error)))
    return msg


def ensure_authenticated_config(config, config_filename, session,
                                use_new_format=False):
    try:
        session.authenticate(config.auth)
    except requests.exceptions.SSLError as e:
        humanize_ssl_error_and_die(e, config.store_url)
    except AuthFailedError as exc:
        msg = _invalid_authentication_message(config.auth, exc)
        print(msg)
        print("\nYou can change your authentication details with "
              "'enpkg --userpass'.")
        sys.exit(-1)
    else:
        if not use_new_format:
            convert_auth_if_required(config_filename)


def configure_authentication_or_exit(config, config_filename,
                                     session):
    n_trials = 3
    for i in range(n_trials):
        username, password = input_auth()
        if username:
            break
        else:
            msg = "Please enter a non empty username ({0} trial(s) left, " \
                  "Ctrl+C to exit)". format(n_trials - i - 1)
            print(msg)
    else:
        print("No valid username entered (no modification was written).")
        sys.exit(-1)

    auth = UserPasswordAuth(username, password)

    try:
        config._checked_change_auth(auth, session, config_filename)
    except AuthFailedError as exc:
        msg = _invalid_authentication_message(auth, exc)
        print(msg)
        print("\nNo modification was written.")
        sys.exit(-1)


def setup_proxy_or_die(config, proxy):
    if proxy:
        try:
            config.update(proxy=proxy)
        except InvalidConfiguration as e:
            print("Error: invalid proxy setting {0!r}".format(e))
            sys.exit(1)


def dispatch_commands_without_enpkg(args, config, config_filename, prefixes,
                                    prefix, pat, session):
    """
    Returns True if a command has been executed.
    """
    if args.env:                                  # --env
        env_option(prefixes)
        return True

    if args.log:                                  # --log
        print_history(prefix)
        return True

    if args.freeze:
        freeze(prefixes)
        return True

    if args.list:                                 # --list
        list_option(prefixes, pat)
        return True

    if args.config:                               # --config
        print_config(config, session)
        return True

    if args.add_url:                              # --add-url
        add_url(config_filename, config, args.add_url)
        return True

    if args.userpass:                             # --userpass
        configure_authentication_or_exit(config, config_filename,
                                         session)
        return True


def dispatch_commands_with_enpkg(args, enpkg, config, prefix, session, parser,
                                 pat):
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
        revert(enpkg, args.revert)
        return

    # Try to auto-update enstaller
    if config.autoupdate and not args.no_autoupdate:
        if update_enstaller(session, enpkg._remote_repository, args):
            print("Enstaller has been updated.\n"
                  "Please re-run your previous command.")
            return

    if args.search:                               # --search
        search(enpkg._remote_repository, enpkg._installed_repository,
               config, session, pat)
        return

    if args.info:                                 # --info
        if len(args.cnames) != 1:
            parser.error("Option requires one argument (name of package)")
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
        parser.error("Requirement(s) missing")
    elif len(args.cnames) == 2:
        pat = re.compile(r'\d+\.\d+')
        if pat.match(args.cnames[1]):
            args.cnames = ['-'.join(args.cnames)]

    reqs = _compute_reqs(args.cnames)

    # This code assumes we have already upgraded enstaller if needed
    if needs_to_downgrade_enstaller(reqs):
        msg = "Enstaller in requirement list: enstaller will be downgraded !"
        warnings.warn(msg)
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
            reqs = [Requirement('enstaller')]

    if any(req.name == 'epd' for req in reqs):
        if args.remove:
            parser.error("Can't remove 'epd'")
        elif len(reqs) > 1:
            parser.error("Can't combine 'enpkg epd' with other packages.")
        elif not epd_install_confirm(args.yes):
            return

    if args.remove:
        for req in reqs:
            solver = enpkg._solver_factory()
            try:
                request = Request()
                request.remove(req)
                enpkg.execute(solver.resolve(request))
            except EnpkgError as e:
                print(str(e))
    else:
        for req in reqs:
            install_req(enpkg, config, req, args)


def _user_base():
    return getattr(site, "USER_BASE", abs_expanduser('~/.local'))


def _create_parser():
    p = ArgumentParser(description=__doc__)
    p.add_argument('cnames', metavar='NAME', nargs='*',
                   help='package(s) to work on')
    p.add_argument("--add-url", metavar='URL',
                   help="add a repository URL to the configuration file")
    p.add_argument("--insecure", "-k", action="store_true",
                   default=argparse.SUPPRESS,
                   help="Disable SSL cert verification")
    p.add_argument("--config", action="store_true",
                   help="display the configuration and exit")
    p.add_argument("-c", "--config-path",
                   help="Alternative configuration location (must be in the "
                        "new YAML-based format).")
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
    p.add_argument("--max-retries", type=int,
                   default=argparse.SUPPRESS,
                   help="Maximum number of retries for a checksum mismatch or "
                        "a connection error.")
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
                   help="Do nothing, kept for backwarc compatibility.")
    p.add_argument("--sys-prefix", action="store_true",
                   help="use sys.prefix as the install prefix")
    p.add_argument("--update-all", action="store_true",
                   help="update all installed packages")
    p.add_argument("--user", action="store_true",
                   help="install into user prefix, i.e. --prefix=%r" %
                        _user_base())
    p.add_argument("--userpass", action="store_true",
                   help="prompt for Enthought authentication, and save in "
                   "configuration file .enstaller4rc")
    p.add_argument('-v', "--verbose", action="count", default=0,
                   help="Verbose output if specified once, more verbose if "
                        "specified twice, logs sent/received http headers if "
                        "specified thrice.")
    p.add_argument('--version', action="version",
                   version='enstaller version: ' + enstaller.__version__)
    p.add_argument("--whats-new", action="store_true",
                   help="display available updates for installed packages")
    p.add_argument("-y", "--yes", action="store_true",
                   help="Assume 'yes' to all queries and do not prompt.")
    p.add_argument("--no-autoupdate", action="store_true",
                   help="Do not attempt to autoupdate")

    return p


def _compute_reqs(cnames):
    reqs = []
    for arg in cnames:
        if '-' in arg:
            name, version = arg.split('-', 1)
            reqs.append(Requirement(name + ' ' + version))
        else:
            reqs.append(Requirement(arg))
    return reqs


def _enable_logging(verbosity_level):
    if verbosity_level >= 2:
        level = logging.DEBUG
    elif verbosity_level == 1:
        level = logging.INFO
    else:
        level = logging.WARN
    logging.basicConfig(level=level, format="%(message)s")
    if verbosity_level >= 3:
        http_client.HTTPConnection.debuglevel = 1

    msg = ("Using enstaller version {0!r} (git rev {1!r})".
           format(enstaller.__version__, enstaller.__git_revision__))
    logger.info(msg)


def _preprocess_options(argv):
    p = _create_parser()
    args = p.parse_args(argv)

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

    _enable_logging(args.verbose)

    if args.user:
        args.prefix = _user_base()

    if args.prefix and args.sys_prefix:
        p.error("Options --prefix and --sys-prefix exclude each other")

    if args.force and args.forceall:
        p.error("Options --force and --forceall exclude each other")

    return p, args


def _ensure_config_path():
    config_filename = _get_config_candidate()

    if config_filename is None:
        config_filename = HOME_ENSTALLER4RC
        write_default_config(config_filename)
    return config_filename


def _ensure_config_or_die():
    config_filename = _ensure_config_path()

    try:
        config = Configuration.from_file(config_filename)
    except InvalidConfiguration as e:
        print(str(e))
        sys.exit(EXIT_ABORTED)

    return config


def _compute_prefixes(args, config):
    sys_prefix = os.path.normpath(sys.prefix)

    # make prefix
    if args.sys_prefix:
        prefix = sys_prefix
    elif args.prefix:
        prefix = os.path.normpath(args.prefix)
    else:
        prefix = config.prefix

    # now make prefixes
    if prefix == sys_prefix:
        prefixes = [sys_prefix]
    else:
        prefixes = [prefix, sys_prefix]

    return prefix, prefixes


def main(argv=None):
    if argv is None:  # pragma: no cover
        argv = sys.argv[1:]

    parser, args = _preprocess_options(argv)

    pat = None
    if (args.list or args.search) and args.cnames:
        pat = re.compile(args.cnames[0], re.I)

    if args.config_path:
        config_filename = os.path.expanduser(args.config_path)
        try:
            config = Configuration.from_yaml_filename(config_filename)
        except IOError:
            msg = "Error: File {0!r} could not be read".format(config_filename)
            print(msg)
            sys.exit(-1)
        else:
            if config.auth is None:
                print("Authentication missing from {0!r}".format(config_filename))
                sys.exit(-1)
            use_new_format = True
    else:
        config = _ensure_config_or_die()
        config_filename = config.filename
        use_new_format = False

    setup_proxy_or_die(config, args.proxy)

    prefix, prefixes = _compute_prefixes(args, config)
    config.update(prefix=prefix)

    if args.user:
        try:
            check_prefixes(prefixes)
        except InvalidPythonPathConfiguration:
            msg = "Using the --user option, but your PYTHONPATH is not " \
                  "setup accordingly"
            warnings.warn(msg)

    exit_if_root_on_non_owned(args.yes)

    logger.info("prefixes")
    for prefix in prefixes:
        logger.info('    %s%s', prefix, ['', ' (sys)'][prefix == sys.prefix])

    if hasattr(args, "insecure"):
        config.update(verify_ssl=not args.insecure)

    if hasattr(args, "max_retries"):
        config.update(max_retries=args.max_retries)

    with Session.from_configuration(config) as session:
        if dispatch_commands_without_enpkg(args, config, config_filename,
                                           prefixes, prefix, pat,
                                           session):
            return

        if config.auth is None:
            configure_authentication_or_exit(config, config_filename,
                                             session)
        ensure_authenticated_config(config, config_filename, session,
                                    use_new_format=use_new_format)

        repository = repository_factory(session, config.indices, args.quiet)
        if args.quiet:
            progress_bar_context = None
        else:
            def fetch_progress_factory(*a, **kw):
                return console_progress_manager_factory(*a, show_speed=True,
                                                        **kw)

            progress_bar_context = ProgressBarContext(
                console_progress_manager_factory, fetch=fetch_progress_factory)
        enpkg = Enpkg(repository, session, prefixes, progress_bar_context,
                      args.force or args.forceall,
                      max_retries=config.max_retries)

        dispatch_commands_with_enpkg(args, enpkg, config, prefix, session, parser,
                                     pat)


def main_noexc(argv=None):
    # FIXME: re-enable traceback hiding (aka enstaller_debug=False) once
    # we have enstaller logs
    enstaller_debug = True

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
            msg += "\nYou can get a full traceback by setting the " \
                   "ENSTALLER_DEBUG environment variable"
            print(msg % ("enstaller", "enstaller", e.__class__, repr(e)))
            sys.exit(1)

if __name__ == '__main__':  # pragma: no cover
    main_noexc()
