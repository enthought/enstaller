from __future__ import print_function

import collections
import contextlib
import json
import sys

import mock

from egginst.vendor.six import PY2, StringIO

from enstaller.config import Configuration
from enstaller.enpkg import Enpkg
from enstaller.plat import custom_plat
from enstaller.repository import (InstalledPackageMetadata, Repository,
                                  RepositoryPackageMetadata)
from enstaller.session import Session
from enstaller.utils import PY_VER
from enstaller.vendor import responses
from enstaller.versions.enpkg import EnpkgVersion


FAKE_MD5 = "a" * 32
FAKE_SIZE = -1


R_JSON_AUTH_RESP = {
    'first_name': u'David',
    'has_subscription': True,
    'is_active': True,
    'is_authenticated': True,
    'last_name': u'Cournapeau',
    'subscription_level': u'basic'
}

R_JSON_AUTH_FREE_RESP = {
    'first_name': u'David',
    'has_subscription': False,
    'is_active': True,
    'is_authenticated': True,
    'last_name': u'Cournapeau',
    'subscription_level': u'free'
}

R_JSON_NOAUTH_RESP = {
    'is_authenticated': False,
    'last_name': u'Cournapeau',
    'first_name': u'David',
    'has_subscription': True,
    'subscription_level': u'basic'
}

SIMPLE_INDEX = {
    "nose-1.3.4-1.egg": {
        "available": True,
        "build": 1,
        "md5": "7fbd5a7c83ebbb14c42141ed734505ef",
        "mtime": 1409944509.0,
        "name": "nose",
        "product": "free",
        "python": None,
        "size": 334992,
        "type": "egg",
        "version": "1.3.4"
    },
}


if sys.version_info < (2, 7):
    # FIXME: this looks quite fishy. On 2.6, with unittest2, the assertRaises
    # context manager does not contain the actual exception object ?
    def exception_code(ctx):
        return ctx.exception
else:
    def exception_code(ctx):
        return ctx.exception.code


class DummyAuthenticator(object):
    def __init__(self, user_info=None):
        self._auth = None

    @property
    def auth(self):
        return self._auth

    def authenticate(self, session, auth):
        self._auth = auth


def dummy_installed_package_factory(name, version, build, key=None,
                                    py_ver=PY_VER, store_location=""):
    key = key if key else "{0}-{1}-{2}.egg".format(name, version, build)
    version = EnpkgVersion.from_upstream_and_build(version, build)
    return InstalledPackageMetadata(key, name.lower(), version, [], py_ver,
                                    "", store_location)


def dummy_repository_package_factory(name, version, build, key=None,
                                     py_ver=PY_VER, store_location="",
                                     dependencies=None, mtime=0.0):
    dependencies = dependencies or []
    key = key if key else "{0}-{1}-{2}.egg".format(name, version, build)
    fake_size = FAKE_SIZE
    fake_md5 = FAKE_MD5
    fake_mtime = mtime
    version = EnpkgVersion.from_upstream_and_build(version, build)
    return RepositoryPackageMetadata(key, name.lower(), version,
                                     dependencies, py_ver, fake_size,
                                     fake_md5, fake_mtime, "commercial",
                                     True, store_location)


def repository_factory(entries):
    repository = Repository()
    for entry in entries:
        repository.add_package(entry)
    return repository


class MockedPrint(object):
    def __init__(self):
        self.s = StringIO()

    def __call__(self, *a):
        self.s.write(" ".join(str(_) for _ in a) + "\n")

    @property
    def value(self):
        return self.s.getvalue()


@contextlib.contextmanager
def mock_print():
    m = MockedPrint()

    if PY2:
        with mock.patch("__builtin__.print", m):
            yield m
    else:
        with mock.patch("builtins.print", m):
            yield m


@contextlib.contextmanager
def mock_input(input_string):
    def f(ignored):
        return input_string

    if PY2:
        with mock.patch("__builtin__.raw_input", f):
            yield f
    else:
        with mock.patch("builtins.input", f):
            yield f


# Decorators to force a certain configuration
def make_keyring_unavailable(f):
    return mock.patch("enstaller.config.keyring", None)(f)


# Context managers to force certain configuration
@contextlib.contextmanager
def make_keyring_unavailable_context():
    with mock.patch("enstaller.config.keyring", None) as context:
        yield context


# Context managers to force certain configuration
@contextlib.contextmanager
def make_keyring_available_context():
    m = mock.Mock(["get_password", "set_password"])
    with mock.patch("enstaller.config.keyring", m) as context:
        yield context


@contextlib.contextmanager
def make_default_configuration_path(path):
    with mock.patch("enstaller.main.get_config_filename",
                    lambda ignored: path) as context:
        yield context


@contextlib.contextmanager
def mock_input_auth(username, password):
    with mock.patch("enstaller.main.input_auth",
                    return_value=(username, password)) as context:
        yield context


class _FakeKeyring(object):
    def __init__(self):
        self._state = collections.defaultdict(dict)

    def get_password(self, service, username):
        if service in self._state:
            return self._state[service].get(username, None)
        else:
            return None

    def set_password(self, service, username, password):
        self._state[service][username] = password


@contextlib.contextmanager
def fake_keyring_context():
    keyring = _FakeKeyring()
    with mock.patch("enstaller.config.keyring.get_password",
                    keyring.get_password):
        with mock.patch("enstaller.config.keyring.set_password",
                        keyring.set_password):
            yield keyring


def fake_keyring(f):
    keyring = _FakeKeyring()
    dec1 = mock.patch("enstaller.config.keyring.get_password",
                      keyring.get_password)
    dec2 = mock.patch("enstaller.config.keyring.set_password",
                      keyring.set_password)
    return dec1(dec2(f))


@contextlib.contextmanager
def mock_history_get_state_context(state=None):
    if state is None:
        state = set()
    with mock.patch("enstaller.enpkg.History") as context:
        context.return_value.get_state.return_value = set(state)
        yield context


@contextlib.contextmanager
def mock_raw_input(return_value):
    def _function(message):
        print(message)
        return return_value

    with mock.patch("enstaller.utils.input",
                    side_effect=_function) as context:
        yield context


def unconnected_enpkg_factory(prefixes=None):
    """
    Create an Enpkg instance which does not require an authenticated
    repository.
    """
    if prefixes is None:
        prefixes = [sys.prefix]
    config = Configuration()
    repository = Repository()
    return Enpkg(repository, mocked_session_factory(config.repository_cache),
                 prefixes=prefixes)


def mocked_session_factory(repository_cache):
    return Session(DummyAuthenticator(), repository_cache)


def create_repositories(remote_entries=None, installed_entries=None):
    if remote_entries is None:
        remote_entries = []
    if installed_entries is None:
        installed_entries = []

    remote_repository = Repository()
    for remote_entry in remote_entries:
        remote_repository.add_package(remote_entry)
    installed_repository = Repository()
    for installed_entry in installed_entries:
        installed_repository.add_package(installed_entry)

    return remote_repository, installed_repository


class FakeOptions(object):
    def __init__(self):
        self.force = False
        self.forceall = False
        self.no_deps = False
        self.yes = False


def create_prefix_with_eggs(config, prefix, installed_entries=None,
                            remote_entries=None):
    if remote_entries is None:
        remote_entries = []
    if installed_entries is None:
        installed_entries = []

    repository = repository_factory(remote_entries)

    enpkg = Enpkg(repository, mocked_session_factory(config.repository_cache),
                  prefixes=[prefix])
    for package in installed_entries:
        package.store_location = prefix
        enpkg._top_installed_repository.add_package(package)
        enpkg._installed_repository.add_package(package)
    return enpkg


def mock_index(index_data, store_url="https://api.enthought.com"):
    def decorator(f):
        @responses.activate
        def wrapped(*a, **kw):
            responses.add(responses.GET,
                          "{0}/accounts/user/info/".format(store_url),
                          body=json.dumps(R_JSON_AUTH_RESP))
            url = "{0}/eggs/{1}/index.json"
            responses.add(responses.GET,
                          url.format(store_url, custom_plat),
                          body=json.dumps(index_data))
            return f(*a, **kw)
        return wrapped
    return decorator


@fake_keyring
def authenticated_config(f):
    config = Configuration()
    config.update(auth=("dummy", "dummy"))

    m = mock.Mock()
    m.return_value = config
    m.from_file.return_value = config

    wrapper = mock.patch("enstaller.main.Configuration", m)
    mock_authenticated_config = mock.patch(
        "enstaller.main.ensure_authenticated_config",
        mock.Mock())
    return mock_authenticated_config(wrapper(f))
