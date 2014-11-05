import contextlib
import functools
import os
import tempfile

import mock

from egginst._compat import PY2

from enstaller.config import Configuration
from enstaller.repository import Repository
from enstaller.plat import custom_plat
from enstaller.tests.common import (authenticated_config,
                                    dummy_repository_package_factory)
from enstaller.vendor import responses


def _dont_write_default_configuration(f):
    return mock.patch("enstaller.main.write_default_config",
                      lambda filename, use_keyring=None: None)(f)


def without_any_configuration(f):
    """
    When this decorator is applied, enstaller.main will behave as if no default
    configuration is found anywhere, and no default configuration will be
    written in $HOME.
    """
    @functools.wraps(f)
    def wrapper(*a, **kw):
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            pass
        try:
            with mock.patch("enstaller.main._ensure_config_path",
                            return_value=fp.name):
                return f(*a, **kw)
        finally:
            os.unlink(fp.name)
    return wrapper


def mock_install_req(f):
    """
    Decorating a function/class with this decorator will mock install_req
    completely within enstaller.main function.
    """
    return mock.patch("enstaller.main.install_req", mock.Mock())(f)


def fake_empty_resolve(f):
    @functools.wraps(f)
    def wrapper(*a, **kw):
        with mock.patch("enstaller.enpkg.Solver.resolve", return_value=[]):
            return f(*a, **kw)
    return wrapper


def empty_index(f):
    @functools.wraps(f)
    def wrapper(*a, **kw):
        with mock.patch("enstaller.main.repository_factory",
                        return_value=Repository()):
            return f(*a, **kw)
    return wrapper


@contextlib.contextmanager
def set_env_vars(**kw):
    old_env = os.environ.copy()
    try:
        yield os.environ.update(**kw)
    finally:
        os.environ = old_env


@contextlib.contextmanager
def use_given_config_context(filename):
    """
    When this decorator is applied, enstaller.main will use the given filename
    as its configuration file.
    """
    with mock.patch("enstaller.main._ensure_config_path",
                    return_value=filename) as context:
        yield context


def fake_configuration_and_auth(f):
    config = Configuration()
    config.update(auth=("john", "doe"))
    @functools.wraps(f)
    @responses.activate
    def wrapper(*a, **kw):
        responses.add(responses.GET,
                      "https://api.enthought.com/eggs/{0}/index.json". \
                        format(custom_plat),
                      body="{}", status=200,
                      content_type='application/json')

        # FIXME: we create a dummy store to bypass store authentication in
        # Enpkg ctor. Will be fixed once Enpkg, repository, stores are clearly
        # separated.
        with mock.patch("enstaller.main.Configuration.from_file",
                        return_value=config):
            with mock.patch("enstaller.main.ensure_authenticated_config",
                            return_value=True):
                return without_any_configuration(f)(*a, **kw)
    return wrapper


def enstaller_version(version, is_released=True):
    wrap1 = mock.patch("enstaller.__version__", version)
    wrap2 = mock.patch("enstaller.__is_released__", is_released)
    def dec(f):
        return wrap1(wrap2(f))
    return dec

def remote_enstaller_available(versions):
    repository = Repository()
    for version in versions:
        package = dummy_repository_package_factory("enstaller", version, build=1)
        repository.add_package(package)

    def dec(f):
        @functools.wraps(f)
        def wrapper(*a, **kw):
            with mock.patch("enstaller.main.repository_factory",
                            return_value=repository):
                return f(*a, **kw)
        return wrapper
    return dec

def raw_input_always_yes(f):
    if PY2:
        wrap = mock.patch("__builtin__.raw_input", lambda ignored: "y")
    else:
        wrap = mock.patch("builtins.input", lambda ignored: "y")
    return wrap(f)
