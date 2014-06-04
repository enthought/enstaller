import os
import os.path
import shutil
import sys
import tempfile
import threading

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from encore.events.event_manager import EventManager

from egginst.tests.common import _EGGINST_COMMON_DATA

from enstaller.errors import EnstallerException
from enstaller.fetch import DownloadManager
from enstaller.repository import Repository, RepositoryPackageMetadata
from enstaller.utils import compute_md5

from enstaller.tests.common import mock_url_fetcher


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

    def test_fetch_simple(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)
        repository = self._create_store_and_repository([filename])

        # When
        fetch_api = DownloadManager(repository, self.tempdir)
        with mock_url_fetcher(fetch_api, open(path, "rb")):
            fetch_api.fetch_egg(filename)

        # Then
        target = os.path.join(self.tempdir, filename)
        self.assertTrue(os.path.exists(target))
        self.assertEqual(compute_md5(target),
                         repository.find_package("nose", "1.3.0-1").md5)

    def test_fetch_invalid_md5(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)

        repository = self._create_store_and_repository([filename])

        mocked_metadata = mock.Mock()
        mocked_metadata.md5 = "a" * 32
        mocked_metadata.size = 1024
        mocked_metadata.key = filename

        with mock.patch.object(repository, "find_package", return_value=mocked_metadata):
            fetch_api = DownloadManager(repository, self.tempdir)
            with mock_url_fetcher(fetch_api, open(path)):
                # When/Then
                with self.assertRaises(EnstallerException):
                    fetch_api.fetch_egg(filename)

    def test_fetch_abort(self):
        # Given
        event = threading.Event()

        filename = "nose-1.3.0-1.egg"

        repository = self._create_store_and_repository([filename])

        response = MockedStoreResponse(100000, event, 0.5)
        # When
        fetch_api = DownloadManager(repository, self.tempdir)
        with mock_url_fetcher(fetch_api, response):
            fetch_api.fetch_egg(filename, execution_aborted=event)

            # Then
            target = os.path.join(self.tempdir, filename)
            self.assertTrue(event.is_set())
            self.assertFalse(os.path.exists(target))

    def test_fetch_egg_simple(self):
        # Given
        egg = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, egg)

        repository = self._create_store_and_repository([egg])

        # When
        fetch_api = DownloadManager(repository, self.tempdir)
        with mock_url_fetcher(fetch_api, open(path, "rb")):
            fetch_api.fetch_egg(egg)

        # Then
        target = os.path.join(self.tempdir, egg)
        self.assertTrue(os.path.exists(target))
        self.assertEqual(compute_md5(target),
                         compute_md5(os.path.join(_EGGINST_COMMON_DATA, egg)))

    def test_fetch_egg_refetch(self):
        # Given
        egg = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, egg)

        repository = self._create_store_and_repository([egg])

        # When
        fetch_api = DownloadManager(repository, self.tempdir)
        with mock_url_fetcher(fetch_api, open(path, "rb")):
            fetch_api.fetch_egg(egg)

        # Then
        target = os.path.join(self.tempdir, egg)
        self.assertTrue(os.path.exists(target))

    def test_fetch_egg_refetch_invalid_md5(self):
        # Given
        egg = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, egg)

        repository = self._create_store_and_repository([egg])

        def _corrupt_file(target):
            with open(target, "wb") as fo:
                fo.write("")

        # When
        fetch_api = DownloadManager(repository, self.tempdir)
        with mock_url_fetcher(fetch_api, open(path, "rb")):
            fetch_api.fetch_egg(egg)

        # Then
        target = os.path.join(self.tempdir, egg)
        self.assertEqual(compute_md5(target), compute_md5(path))

        # When
        _corrupt_file(target)

        # Then
        self.assertNotEqual(compute_md5(target), compute_md5(path))

        # When
        with mock_url_fetcher(fetch_api, open(path, "rb")):
            fetch_api.fetch_egg(egg, force=True)

        # Then
        self.assertEqual(compute_md5(target), compute_md5(path))

    def test_encore_event_manager(self):
        # Given
        egg = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, egg)
        repository = self._create_store_and_repository([egg])

        with mock.patch.object(EventManager, "emit"):
            event_manager = EventManager()

            # When
            fetch_api = DownloadManager(repository, self.tempdir, evt_mgr=event_manager)
            with mock_url_fetcher(fetch_api, open(path, "rb")):
                fetch_api.fetch_egg(egg)

            # Then
            self.assertTrue(event_manager.emit.called)

    def test_progress_manager(self):
        """
        Ensure that the progress manager __call__ is called inside the fetch
        loop.
        """
        # Given
        egg = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, egg)
        repository = self._create_store_and_repository([egg])

        with mock.patch("egginst.console.ProgressManager") as m:
            # When
            fetch_api = DownloadManager(repository, self.tempdir)
            with mock_url_fetcher(fetch_api, open(path, "rb")):
                fetch_api.fetch_egg(egg)

            # Then
            self.assertTrue(m.called)
