from __future__ import absolute_import, print_function

import errno
import io
import os
import os.path
import sys
import textwrap

from egginst.vendor.six.moves import urllib

from egginst.progress import (console_progress_manager_factory,
                              dummy_progress_bar_factory)

from enstaller.auth import UserInfo
from enstaller.egg_meta import split_eggname
from enstaller.errors import MissingDependency, NoSuchPackage, NoPackageFound
from enstaller.legacy_stores import parse_index
from enstaller.repository import Repository, egg_name_to_name_version
from enstaller.requests_utils import _ResponseIterator
from enstaller.solver import Request, Requirement
from enstaller.utils import decode_json_from_buffer, prompt_yes_no
from enstaller.vendor.futures import ThreadPoolExecutor, as_completed


FMT = '%-20s %-20s %s'
FMT4 = '%-20s %-20s %-20s %s'

DEFAULT_TEXT_WIDTH = 79


def disp_store_info(store_location):
    if not store_location:
        return '-'
    for rm in 'http://', 'https://', 'www', '.enthought.com', '/repo/':
        store_location = store_location.replace(rm, '')
    return store_location.replace('/eggs/', ' ').strip('/')


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
    logged_in_string = config.auth.logged_message
    user_info = UserInfo.from_session(session)
    subscription = user_info.subscription_level
    msg = textwrap.dedent("""\
        Cannot install {0!r}, as this package (or some of its requirements)
        are not available at your subscription level {1!r}
        ({2}).
        """.format(str(requirement), subscription, logged_in_string))
    print()
    print(textwrap.fill(msg, DEFAULT_TEXT_WIDTH))


def _requirement_from_pypi(request, repository):
    are_pypi = []
    for job in request.jobs:
        if job.kind in ("install", "update", "upgrade"):
            try:
                candidate = \
                    repository.find_package_from_requirement(job.requirement)
            except NoSuchPackage:
                pass
            else:
                if candidate.product == "pypi":
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
        print(FMT % (package.name, package.full_version,
                     disp_store_info(package.store_location)))


def _should_raise(resp, raise_on_error):
    if not raise_on_error:
        if resp.status_code in (403, 404):
            return False
    return True


def _print_warning(msg, width=DEFAULT_TEXT_WIDTH):
    preambule = "Warning: "
    wrapper = textwrap.TextWrapper(initial_indent=preambule,
                                   subsequent_indent=len(preambule) * " ",
                                   width=width)
    print(wrapper.fill(msg) + "\n")


def _fetch_repository(session, url, store_location, raise_on_error):
    with session.etag():
        resp = session.get(url, stream=True)
        if resp.status_code != 200:
            if _should_raise(resp, raise_on_error):
                resp.raise_for_status()
            else:
                return None  # failed.append(store_location)
        else:
            data = io.BytesIO()
            for chunk in _ResponseIterator(resp):
                data.write(chunk)
            json_data = decode_json_from_buffer(data.getvalue())
            return Repository(parse_index(json_data, store_location))


def _print_unavailables_warning(unavailables):
    store_names = [_display_store_name(store_location) for store_location in
                   unavailables]
    preambule = "Warning: "
    template = textwrap.dedent("""\
        {0}Could not fetch the following indices:

        {1}
    """)
    displayed = "\n".join("{0}- {1!r}".format(" " * len(preambule), name)
                          for name in store_names)

    after = ("Those repositories do not exist (or you do not have the "
             "rights to access them). You should edit your configuration "
             "to remove those repositories.")
    print(template.format(preambule, displayed))
    wrapper = textwrap.TextWrapper(initial_indent=len(preambule) * " ",
                                   subsequent_indent=len(preambule) * " ",
                                   width=DEFAULT_TEXT_WIDTH)
    print(wrapper.fill(after))
    print()


def _write_and_flush(s, quiet):
    if not quiet:
        sys.stdout.write(s)
        sys.stdout.flush()


def repository_factory(session, indices, quiet=False, raise_on_error=False):
    unavailables = []
    full_repository = Repository()

    _write_and_flush("Fetching indices: ", quiet)

    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = []
        for url, store_location in indices:
            task = executor.submit(_fetch_repository, session, url,
                                   store_location, raise_on_error)
            tasks.append(task)

        for task in as_completed(tasks):
            repository_or_none = task.result()
            if repository_or_none is None:
                unavailables.append(store_location)
            else:
                for package in repository_or_none.iter_packages():
                    full_repository.add_package(package)
            _write_and_flush(".", quiet)

    _write_and_flush("\n\n", quiet)

    if len(unavailables) > 0 and not quiet:
        _print_unavailables_warning(unavailables)
    return full_repository


def name_egg(egg):
    return split_eggname(egg)[0]


def updates_check(remote_repository, installed_repository):
    updates = []
    EPD_update = []
    for package in installed_repository.iter_packages():
        av_metadatas = remote_repository.find_sorted_packages(package.name)
        if len(av_metadatas) == 0:
            continue
        av_metadata = av_metadatas[-1]
        if av_metadata.version > package.version:
            if package.name == "epd":
                EPD_update.append({'current': package, 'update': av_metadata})
            else:
                updates.append({'current': package, 'update': av_metadata})
    return updates, EPD_update


def humanize_ssl_error_and_die(ssl_exception, store_url):
    if ssl_exception.request is not None:
        url = ssl_exception.request.url
    else:
        url = store_url
    p = urllib.parse.urlparse(url)
    print("SSL error: {0}".format(str(ssl_exception)))
    print("To connect to {0!r} insecurely, add the `-k` flag to enpkg "
          "command".format(p.hostname))
    sys.exit(-1)


def is_running_on_non_owned_python():
    """Returns True if the running python process is owned by root
    and sys.executable is owned by a different uid.
    """
    if sys.platform == 'win32':
        return False
    else:
        return (os.getuid() == 0
                and os.stat(sys.executable).st_uid != os.getuid())


def exit_if_root_on_non_owned(force_yes=False):
    if is_running_on_non_owned_python():
        msg = ("You are running enpkg in a python installation not "
               "owned by root, are you sure to continue ? (y/[n])")
        if not prompt_yes_no(msg, force_yes=force_yes):
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
    parts = urllib.parse.urlsplit(store_location)
    return urllib.parse.urlunsplit(("", "", parts[2], parts[3], parts[4]))
