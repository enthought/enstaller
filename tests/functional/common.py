import contextlib
import functools
import os
import tempfile

import mock

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
    def wrapper(ignored):
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            pass
        try:
            dec1 = mock.patch("enstaller.main.get_config_filename",
                              lambda ignored: fp.name)
            ret = dec1(f)
            return ret
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
def use_given_config_context(filename):
    """
    When this decorator is applied, enstaller.main will use the given filename
    as its configuration file.
    """
    with mock.patch("enstaller.main.get_config_filename",
                    lambda ignored: filename) as context:
        yield context
