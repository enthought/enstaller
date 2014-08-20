from __future__ import absolute_import, print_function

import errno
import io
import json
import sys
import textwrap

from egginst._compat import urlparse

from egginst.progress import console_progress_manager_factory

from enstaller.auth import authenticate
from enstaller.egg_meta import split_eggname
from enstaller.errors import NoPackageFound, UnavailablePackage
from enstaller.fetch import URLFetcher
from enstaller.legacy_stores import parse_index
from enstaller.repository import Repository, egg_name_to_name_version
from enstaller.requests_utils import _ResponseIterator
from enstaller.solver import Requirement, comparable_info
from enstaller.utils import prompt_yes_no


FMT = '%-20s %-20s %s'
VB_FMT = '%(version)s-%(build)s'
FMT4 = '%-20s %-20s %-20s %s'

DEFAULT_TEXT_WIDTH = 79


def disp_store_info(info):
    sl = info.get('store_location')
    if not sl:
        return '-'
    for rm in 'http://', 'https://', 'www', '.enthought.com', '/repo/':
        sl = sl.replace(rm, '')
    return sl.replace('/eggs/', ' ').strip('/')


def install_req(enpkg, config, req, opts):
    """
    Try to execute the install actions.
    """
    # Unix exit-status codes
    FAILURE = 1
    req = Requirement.from_anything(req)

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
        solver = enpkg._solver_factory(mode, opts.force, opts.forceall)
        actions = solver.install_actions(req)
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


def install_time_string(installed_repository, name):
    lines = []
    for info in installed_repository.find_packages(name):
        lines.append('%s was installed on: %s' % (info.key, info.ctime))
    return "\n".join(lines)


def print_installed(repository, pat=None):
    print(FMT % ('Name', 'Version', 'Store'))
    print(60 * '=')
    for package in repository.iter_packages():
        if pat and not pat.search(package.name):
            continue
        info = package._compat_dict
        print(FMT % (name_egg(package.key), VB_FMT % info,
              disp_store_info(info)))


def repository_factory(config):
    index_fetcher = URLFetcher(config.repository_cache, config.auth,
                               config.proxy_dict)
    index_fetcher._enable_etag_support()

    repository = Repository()
    for url, store_location in config.indices:
        resp = index_fetcher.fetch(url)
        resp.raise_for_status()

        for package in parse_index(_fetch_json_with_progress(resp,
                                                             store_location),
                                   store_location):
            repository.add_package(package)
    return repository


def name_egg(egg):
    return split_eggname(egg)[0]


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


# Private functions

def _fetch_json_with_progress(resp, store_location):
    data = io.BytesIO()

    length = int(resp.headers.get("content-length", 0))
    display = _display_store_name(store_location)
    progress = console_progress_manager_factory("Fetching index", display,
                                                size=length)
    with progress:
        for chunk in _ResponseIterator(resp):
            data.write(chunk)
            progress.update(len(chunk))

    return json.loads(data.getvalue().decode("utf-8"))


def _display_store_name(store_location):
    parts = urlparse.urlsplit(store_location)
    return urlparse.urlunsplit(("", "", parts[2], parts[3], parts[4]))
