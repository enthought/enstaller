import hashlib
import os
import os.path
import sys
import threading

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from encore.events.event_manager import EventManager

from egginst.tests.common import mkdtemp
from enstaller.fetch import FetchAPI
from enstaller.store.indexed import LocalIndexedStore
from enstaller.utils import compute_md5

class MockedFailingFile(object):
    """
    A file object-like which read may abort when some Thread.Event is set.

    Parameters
    ----------
    size: int
        How large the fake file is
    event: threading.Event
        Instance will be set when abort_threshold will be reached
    abort_threshold: float
        when the internal read pointer reaches abort_threshold * total size,
        event.set() will be called
    """
    def __init__(self, size, event=None, abort_threshold=0):
        self._read_pos = 0
        self.size = size

        self.event = event
        self._failing_count = int(self.size * abort_threshold)

    @property
    def md5(self):
        return hashlib.md5("a" * self.size).hexdigest()

    @property
    def _should_abort(self):
        return self.event is not None and self._read_pos >= self._failing_count

    def read(self, n):
        if self._should_abort:
            self.event.set()

        if self._read_pos < self.size:
            remain = self.size - self._read_pos
            self._read_pos += n
            return "a" * min(n, remain)
        else:
            return None

    def close(self):
        pass

class Entry(object):
    def __init__(self, name, fp):
        self.fp = fp
        self.name = name

    @property
    def metadata_dict(self):
        return {"md5": self.fp.md5, "size": self.fp.size, "name": self.name}

class DummyRepository(LocalIndexedStore):
    def __init__(self, root_dir, entries):
        self.root = root_dir

        self._entries = {}
        self._data = {}

        for entry in entries:
            self._entries[entry.name] = entry.metadata_dict
            self._data[entry.name] = entry.fp

    def get_index(self):
        return self._entries

    def get_data(self, key):
        return self._data[key]

class TestFetchAPI(unittest.TestCase):
    def test_fetch_simple(self):
        with mkdtemp() as d:
            filename = "dummy"
            fp = MockedFailingFile(100000)

            remote = DummyRepository(d, [Entry(filename, fp)])
            remote.connect()

            fetch_api = FetchAPI(remote, d)
            fetch_api.fetch(filename)

            target = os.path.join(d, filename)
            self.assertTrue(os.path.exists(target))
            self.assertEqual(compute_md5(target), fp.md5)

    def test_fetch_invalid_md5(self):
        with mkdtemp() as d:
            filename = "dummy"
            with mock.patch.object(MockedFailingFile, "md5") as mocked_md5:
                mocked_md5.__get__ = lambda *a: hashlib.md5("dummy content").hexdigest()

                fp = MockedFailingFile(100000)

                entry = Entry(filename, fp)
                remote = DummyRepository(d, [entry])
                remote.connect()

                fetch_api = FetchAPI(remote, d)
                with self.assertRaises(ValueError):
                    fetch_api.fetch(filename)

    def test_fetch_abort(self):
        event = threading.Event()

        with mkdtemp() as d:
            filename = "dummy"
            fp = MockedFailingFile(100000, event, 0.5)

            remote = DummyRepository(d, [Entry(filename, fp)])
            remote.connect()

            fetch_api = FetchAPI(remote, d)
            fetch_api.fetch(filename, event)

            target = os.path.join(d, filename)
            self.assertTrue(event.is_set())
            self.assertFalse(os.path.exists(target))

    def test_fetch_egg_simple(self):
        with mkdtemp() as d:
            egg = "dummy-1.0.0-1.egg"
            fp = MockedFailingFile(100000)

            remote = DummyRepository(d, [Entry(egg, fp)])
            remote.connect()

            fetch_api = FetchAPI(remote, d)
            fetch_api.fetch_egg(egg)

            target = os.path.join(d, egg)
            self.assertTrue(os.path.exists(target))

    def test_fetch_egg_refetch(self):
        with mkdtemp() as d:
            egg = "dummy-1.0.0-1.egg"
            fp = MockedFailingFile(100000)

            remote = DummyRepository(d, [Entry(egg, fp)])
            remote.connect()

            fetch_api = FetchAPI(remote, d)
            fetch_api.fetch_egg(egg)

            target = os.path.join(d, egg)
            self.assertTrue(os.path.exists(target))

            fetch_api.fetch_egg(egg)

    def test_fetch_egg_refetch_invalid_md5(self):
        with mkdtemp() as d:
            egg = "dummy-1.0.0-1.egg"

            def _fetch_api_factory():
                fp = MockedFailingFile(100000)

                remote = DummyRepository(d, [Entry(egg, fp)])
                remote.connect()

                return fp, FetchAPI(remote, d)

            def _corrupt_file(target):
                with open(target, "wb") as fo:
                    fo.write("")

            fp, fetch_api = _fetch_api_factory()
            fetch_api.fetch_egg(egg)

            target = os.path.join(d, egg)

            self.assertEqual(compute_md5(target), fp.md5)
            _corrupt_file(target)
            self.assertNotEqual(compute_md5(target), fp.md5)

            fp, fetch_api = _fetch_api_factory()
            fetch_api.fetch_egg(egg, force=True)

            self.assertEqual(compute_md5(target), fp.md5)

    def test_encore_event_manager(self):
        with mkdtemp() as d:
            with mock.patch.object(EventManager, "emit"):
                event_manager = EventManager()

                egg = "yoyo-1.0.0-1.egg"
                fp = MockedFailingFile(1024 * 32)

                remote = DummyRepository(d, [Entry(egg, fp)])
                remote.connect()

                fetch_api = FetchAPI(remote, d, event_manager)
                fetch_api.fetch_egg(egg)

                self.assertTrue(event_manager.emit.called)

    def test_progress_manager(self):
        """
        Ensure that the progress manager __call__ is called inside the fetch
        loop.
        """
        with mkdtemp() as d:
            with mock.patch("egginst.console.ProgressManager") as m:
                egg = "yoyo-1.0.0-1.egg"
                fp = MockedFailingFile(1024 * 32)

                remote = DummyRepository(d, [Entry(egg, fp)])
                remote.connect()

                fetch_api = FetchAPI(remote, d)
                fetch_api.fetch_egg(egg)

                self.assertTrue(m.called)
