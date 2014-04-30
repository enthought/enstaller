import contextlib
import functools
import os
import tempfile

import mock

from okonomiyaki.repositories.enpkg import EnpkgS3IndexEntry

from enstaller.config import Configuration
from enstaller.store.tests.common import MetadataOnlyStore
from enstaller.tests.common import fake_keyring, succeed_authenticate

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
            dec = mock.patch("enstaller.main.get_config_filename",
                              lambda ignored: fp.name)
            return dec(f)(*a, **kw)
        finally:
            os.unlink(fp.name)
    return wrapper


def mock_enpkg_class(f):
    """
    Decorating a function/class with this decorator will mock Enpkg completely
    within enstaller.main function.
    """
    dec1 = mock.patch("enstaller.main.Enpkg", mock.Mock())
    dec2 = mock.patch("enstaller.main.install_req", mock.Mock())
    return dec1(dec2(f))


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
    with mock.patch("enstaller.main.get_config_filename",
                    lambda ignored: filename) as context:
        yield context


def fake_configuration_and_auth(f):
    config = Configuration()
    config.set_auth("john", "doe")
    @functools.wraps(f)
    def wrapper(*a, **kw):
        # FIXME: we create a dummy store to bypass store authentication in
        # Enpkg ctor. Will be fixed once Enpkg, repository, stores are clearly
        # separated.
        with mock.patch("enstaller.main.get_default_remote"):
            with mock.patch("enstaller.main.Configuration.from_file",
                            return_value=config):
                with mock.patch("enstaller.main.ensure_authenticated_config",
                                return_value=True):
                    return without_any_configuration(f)(*a, **kw)
    return wrapper


def enstaller_version(version, is_released=True):
    wrap1 = mock.patch("enstaller.__version__", version)
    wrap2 = mock.patch("enstaller.main.__ENSTALLER_VERSION__", version)
    wrap3 = mock.patch("enstaller.main.IS_RELEASED", is_released)
    def dec(f):
        return wrap1(wrap2(wrap3(f)))
    return dec

@fake_keyring
def authenticated_config(f):
    config = Configuration()
    config.set_auth("dummy", "dummy")

    m = mock.Mock()
    m.return_value = config
    m.from_file.return_value = config

    wrapper = mock.patch("enstaller.main.Configuration", m)
    mock_authenticated_config = mock.patch(
        "enstaller.main.ensure_authenticated_config",
         mock.Mock())
    return mock_authenticated_config(wrapper(f))

def remote_enstaller_available(versions):
    enstaller_eggs = [
        EnpkgS3IndexEntry(product="free", build=1,
                          egg_basename="enstaller", version=version,
                          available=True)
        for version in versions
    ]
    store = MetadataOnlyStore(enstaller_eggs)

    wrap = mock.patch("enstaller.main.get_default_remote", lambda ignored: store)
    def dec(f):
        return wrap(f)
    return dec

def raw_input_always_yes(f):
    wrap = mock.patch("__builtin__.raw_input", lambda ignored: "y")
    return wrap(f)
