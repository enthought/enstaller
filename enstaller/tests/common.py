from __future__ import print_function

from egginst._compat import PY2, StringIO

import collections
import contextlib
import sys

import mock

from enstaller.auth import UserInfo
from enstaller.config import Configuration
from enstaller.enpkg import Enpkg
from enstaller.errors import AuthFailedError
from enstaller.repository import (InstalledPackageMetadata, Repository,
                                  RepositoryPackageMetadata)
from enstaller.utils import PY_VER


FAKE_MD5 = "a" * 32
FAKE_SIZE = -1


def dummy_installed_package_factory(name, version, build, key=None,
                                    py_ver=PY_VER, store_location=""):
    key = key if key else "{0}-{1}-{2}.egg".format(name, version, build)
    return InstalledPackageMetadata(key, name.lower(), version, build, [], py_ver,
                                    "", store_location)

def dummy_repository_package_factory(name, version, build, key=None,
                                     py_ver=PY_VER, store_location="",
                                     dependencies=None):
    dependencies = dependencies or []
    key = key if key else "{0}-{1}-{2}.egg".format(name, version, build)
    fake_size = FAKE_SIZE
    fake_md5 = FAKE_MD5
    fake_mtime = 0.0
    return RepositoryPackageMetadata(key, name.lower(), version, build,
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
def is_authenticated(f):
    w1 = mock.patch("enstaller.cli.utils.authenticate",
                     lambda ignored: UserInfo(True))
    w2 = mock.patch("enstaller.config.authenticate",
                     lambda ignored: UserInfo(True))
    return w1(w2(f))


def is_not_authenticated(f):
    return mock.patch("enstaller.main.authenticate",
                      lambda ignored: UserInfo(False))(f)

def make_keyring_unavailable(f):
    return mock.patch("enstaller.config.keyring", None)(f)

def fail_authenticate(f):
    m = mock.Mock(side_effect=AuthFailedError("Dummy auth error"))
    main = mock.patch("enstaller.main.authenticate", m)
    config = mock.patch("enstaller.config.authenticate", m)
    return main(config(f))

def succeed_authenticate(f):
    fake_user = {"first_name": "John", "last_name": "Doe",
                 "has_subscription": True}
    m = mock.Mock(return_value=fake_user)
    main = mock.patch("enstaller.main.authenticate", m)
    config = mock.patch("enstaller.config.authenticate", m)
    return main(config(f))

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
    return Enpkg(repository, mock_fetcher_factory(config.repository_cache),
                 prefixes=prefixes)

def mock_fetcher_factory(repository_cache):
    mocked_fetcher = mock.Mock()
    mocked_fetcher.cache_dir = repository_cache
    return mocked_fetcher


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

    enpkg = Enpkg(repository, mock_fetcher_factory(config.repository_cache),
                  prefixes=[prefix])
    for package in installed_entries:
        package.store_location = prefix
        enpkg._top_installed_repository.add_package(package)
        enpkg._installed_repository.add_package(package)
    return enpkg
