import os.path
import shutil
import sys
import threading
import tempfile
import time

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from encore.events.event_manager import EventManager

from egginst.tests.common import _EGGINST_COMMON_DATA

from enstaller.enpkg import Enpkg
from enstaller.fetch import DownloadManager
from enstaller.repository import Repository, RepositoryPackageMetadata

from enstaller.tests.common import mock_url_fetcher
from .common import dummy_repository_package_factory, repository_factory


class MockedStoreResponse(object):
    """
    A StoreResponse-like object which read may abort when some Thread.Event is
    set.

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
    def _should_abort(self):
        return self.event is not None and self._read_pos >= self._failing_count

    def iter_content(self):
        while True:
            chunk = self.read(1024)
            if chunk is None:
                break
            else:
                yield chunk

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


class TestEnpkg(unittest.TestCase):
    @unittest.expectedFailure
    def test_abort(self):
        """Ensure calling abort does abort the current set of executed actions."""
        sentinel = []

        def fake_install(*args):
            time.sleep(5)
            sentinel.append("oui oui")

        entries = [
            dummy_repository_package_factory("numpy", "1.6.1", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
        ]
        repository = repository_factory(entries)

        with mock.patch("enstaller.enpkg.FetchAction.execute"):
            with mock.patch("enstaller.enpkg.InstallAction.execute", fake_install):
                enpkg = Enpkg(repository, mock.Mock())
                actions = enpkg._solver.install_actions("numpy")

                t = threading.Thread(target=lambda: enpkg.execute(actions))
                t.start()

                enpkg.abort_execution()
                t.join(timeout=10)

        self.assertEqual(sentinel, [])


class TestDownloadManager(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _create_store_and_repository(self, eggs):
        repository = Repository()
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RepositoryPackageMetadata.from_egg(path)
            repository.add_package(package)

        return repository

    @unittest.expectedFailure
    def test_encore_event_manager(self):
        # Given
        egg = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, egg)
        repository = self._create_store_and_repository([egg])

        with mock.patch.object(EventManager, "emit"):
            event_manager = EventManager()

            # When
            downloader = DownloadManager(repository, self.tempdir, evt_mgr=event_manager)
            with mock_url_fetcher(downloader, open(path, "rb")):
                downloader.fetch(egg)

            # Then
            self.assertTrue(event_manager.emit.called)

    @unittest.expectedFailure
    def test_fetch_abort(self):
        # Given
        event = threading.Event()

        filename = "nose-1.3.0-1.egg"

        repository = self._create_store_and_repository([filename])

        response = MockedStoreResponse(100000, event, 0.5)
        # When
        downloader = DownloadManager(repository, self.tempdir,
                                     execution_aborted=event)
        with mock_url_fetcher(downloader, response):
            downloader.fetch(filename)

            # Then
            target = os.path.join(self.tempdir, filename)
            self.assertTrue(event.is_set())
            self.assertFalse(os.path.exists(target))
