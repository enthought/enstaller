from __future__ import absolute_import, print_function

import errno
import io
import json
import sys
import textwrap

from egginst._compat import urlparse

from egginst.progress import (console_progress_manager_factory,
                              dummy_progress_bar_factory)

from enstaller.auth import UserInfo
from enstaller.egg_meta import split_eggname
from enstaller.errors import MissingDependency, NoPackageFound, UnavailablePackage
from enstaller.legacy_stores import parse_index
from enstaller.repository import Repository, egg_name_to_name_version
from enstaller.requests_utils import _ResponseIterator
from enstaller.solver import Request, Requirement, comparable_info
from enstaller.utils import decode_json_from_buffer, prompt_yes_no


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


def _is_any_package_unavailable(remote_repository, actions):
    unavailables = []
    for opcode, egg in actions:
        if opcode == "install":
            name, version = egg_name_to_name_version(egg)
            package = remote_repository.find_package(name, version)
            if not package.available:
                unavailables.append(egg)
    return len(unavailables) > 0


def _notify_unavailable_package(config, requirement, session):
    username, __ = config.auth
    user_info = UserInfo.from_session(session)
    subscription = user_info.subscription_level
    msg = textwrap.dedent("""\
        Cannot install {0!r}, as this package (or some of its requirements)
        are not available at your subscription level {1!r} (You are
        currently logged in as {2!r}).
        """.format(str(requirement), subscription, username))
    print()
    print(textwrap.fill(msg, DEFAULT_TEXT_WIDTH))


def _requirement_from_pypi(request, repository):
    are_pypi = []
    for job in request.jobs:
        if job.kind in ("install", "update", "upgrade"):
            candidates = repository.find_packages(job.requirement.name)
            if len(candidates) > 0 \
                    and any(candidate.product == "pypi"
                            for candidate in candidates):
                are_pypi.append(job.requirement)
    return are_pypi


_BROKEN_PYPI_TEMPLATE = """
Broken pypi package '{requested}': missing dependency '{dependency}'

Pypi packages are not officially supported. If this package is important to
you, please contact Enthought support to request its inclusion in our
officially supported repository.

In the mean time, you may want to try installing '{requested}' from sources
with pip as follows:

    $ enpkg pip
    $ pip install <requested_package>
"""

def install_req(enpkg, config, req, opts):
    """
    Try to execute the install actions.
    """
    # Unix exit-status codes
    FAILURE = 1
    req = Requirement.from_anything(req)
    request = Request()
    request.install(req)

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

    def _ask_pypi_confirmation(package_list_string):
        msg = textwrap.dedent("""\
        The following packages/requirements are coming from the PyPi repo:

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

        msg = "Are you sure that you wish to proceed?  (y/[n])"
        if not prompt_yes_no(msg, opts.yes):
            sys.exit(0)

    def _ask_pypi_confirmation_from_actions(actions):
        unsupported_packages = _get_unsupported_packages(actions)
        if len(unsupported_packages) > 0:
            package_list = sorted("'{0}-{1}'".format(p.name, p.full_version)
                                  for p in unsupported_packages)
            package_list_string = "\n".join(package_list)
            _ask_pypi_confirmation(package_list_string)

    try:
        mode = 'root' if opts.no_deps else 'recur'
        pypi_asked = False
        solver = enpkg._solver_factory(mode, opts.force, opts.forceall)

        pypi_requirements = _requirement_from_pypi(request,
                                                   enpkg._remote_repository)

        try:
            actions = solver.resolve(request)
        except MissingDependency as e:
            if len(pypi_requirements) > 0:
                msg = _BROKEN_PYPI_TEMPLATE.format(requested=e.requester,
                        dependency=e.requirement)
                print(msg)
            else:
                print("One of the requested package has broken dependencies")
                print("(Dependency solving error: {0})".format(e))
            _done(FAILURE)

        if len(pypi_requirements) > 0:
            package_list = sorted(str(p) for p in pypi_requirements)
            _ask_pypi_confirmation("\n".join(package_list))
            pypi_asked = True

        installed = (egg for opcode, egg in actions if opcode == "install")
        actions = [("fetch", egg) for egg in installed] + actions

        if _is_any_package_unavailable(enpkg._remote_repository, actions):
            _notify_unavailable_package(config, req, enpkg._session)
            _done(FAILURE)
        if not pypi_asked:
            _ask_pypi_confirmation_from_actions(actions)
        enpkg.execute(actions)
        if len(actions) == 0:
            print("No update necessary, %r is up-to-date." % req.name)
            print(install_time_string(enpkg._installed_repository,
                                      req.name))
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


def repository_factory(session, indices, quiet=False):
    repository = Repository()
    for url, store_location in indices:
        with session.etag():
            resp = session.fetch(url)
            for package in parse_index(_fetch_json_with_progress(resp,
                                                                store_location,
                                                                quiet),
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


def humanize_ssl_error_and_die(ssl_exception, store_url):
    if ssl_exception.request is not None:
        url = ssl_exception.request.url
    else:
        url = store_url
    p = urlparse.urlparse(url)
    print("To connect to {0!r} insecurely, add the `-k` flag to enpkg "
          "command".format(p.hostname))
    sys.exit(-1)


# Private functions
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

    data = data.getvalue()
    return decode_json_from_buffer(data)


def _display_store_name(store_location):
    parts = urlparse.urlsplit(store_location)
    return urlparse.urlunsplit(("", "", parts[2], parts[3], parts[4]))
