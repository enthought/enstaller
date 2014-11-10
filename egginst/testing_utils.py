from __future__ import print_function

import contextlib
import functools
import logging
import os

logger = logging.getLogger(__name__)


def slow(t):
    """
    Label a test as slow.

    Parameters
    ----------
    t : callable
        The test requiring network connectivity.

    Returns
    -------
    t : callable
        The decorated test `t`.
    """
    t.slow = True

    @functools.wraps(t)
    def slow_wrapper(*args, **kwargs):
        return t(*args, **kwargs)

    return slow_wrapper


class ControlledEnv(object):
    """
    A special os.environ that can be used for mocking os.environ.

    Beyond avoiding modifying os.environ directly, this class allows some keys
    to be ignored

    Parameters
    ----------
    ignored_keys: list
        If specified, list of keys that will be ignored.
    environ: dict
        If specified, the dictionary to use for underlying data. Default is to
        use os.environ. In both cases, the dict is copied.

    Examples
    --------
    >>> env = ControlledEnv(["USERNAME"])
    >>> "USERNAME" in env:
    False
    """

    def __init__(self, ignored_keys=None, environ=None):
        if ignored_keys is None:
            ignored_keys = set()
        self._ignored_keys = ignored_keys

        if environ is None:
            self._data = os.environ.copy()
        else:
            self._data = environ.copy()

    def __getitem__(self, name):
        if name in self._ignored_keys:
            raise KeyError("Cannot access key {0}".format(name))
        else:
            return self._data[name]

    def get(self, name, default=None):
        if name in self._data and name not in self._ignored_keys:
            return self._data[name]
        else:
            return default

    def keys(self):
        return [k for k in self._data if k not in self._ignored_keys]

    def __contains__(self, key):
        return key not in self._ignored_keys and key in self._data

    def __setitem__(self, name, value):
        self._data[name] = value


@contextlib.contextmanager
def assert_same_fs(test_case, prefix):
    all_files = []
    for root, dirs, files in os.walk(prefix):
        for f in files:
            all_files.extend(os.path.join(root, f) for f in files)
    old_state = set(all_files)

    yield

    for root, dirs, files in os.walk(prefix):
        for f in files:
            path = os.path.join(root, f)
            if path not in old_state:
                test_case.fail("Unexpected file: {0!r}".format(path))
