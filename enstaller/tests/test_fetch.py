import os
import os.path
import shutil
import tempfile

from egginst.tests.common import _EGGINST_COMMON_DATA
from egginst.vendor.six.moves import unittest

from enstaller.vendor import requests, responses

from enstaller.errors import InvalidChecksum
from enstaller.fetch import _DownloadManager
from enstaller.repository import Repository, RepositoryPackageMetadata
from enstaller.utils import compute_md5

from enstaller.tests.common import mocked_session_factory


class Test_DownloadManager(unittest.TestCase):
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
        repository = self._create_store_and_repository([filename])

        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        downloader.fetch(filename)

        # Then
        target = os.path.join(self.tempdir, filename)
        self.assertTrue(os.path.exists(target))
        self.assertEqual(compute_md5(target),
                         repository.find_package("nose", "1.3.0-1").md5)

    def test_fetch_invalid_md5(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)

        repository = Repository()
        package = RepositoryPackageMetadata.from_egg(path)
        package.md5 = "a" * 32
        repository.add_package(package)

        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        with self.assertRaises(InvalidChecksum):
            downloader.fetch(filename)

    def test_fetch_abort(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        repository = self._create_store_and_repository([filename])

        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        target = os.path.join(self.tempdir, filename)

        # When
        context = downloader.iter_fetch(filename)
        for i, chunk in enumerate(context):
            if i == 1:
                context.cancel()
                break

        # Then
        self.assertFalse(os.path.exists(target))

    def test_fetch_egg_refetch(self):
        # Given
        egg = "nose-1.3.0-1.egg"

        repository = self._create_store_and_repository([egg])

        # When
        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        downloader.fetch(egg)

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
                fo.write(b"")

        # When
        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        downloader.fetch(egg)

        # Then
        target = os.path.join(self.tempdir, egg)
        self.assertEqual(compute_md5(target), compute_md5(path))

        # When
        _corrupt_file(target)

        # Then
        self.assertNotEqual(compute_md5(target), compute_md5(path))

        # When
        downloader.fetch(egg, force=True)

        # Then
        self.assertEqual(compute_md5(target), compute_md5(path))

        # When/Then
        # Ensure we deal correctly with force=False when the egg is already
        # there.
        downloader.fetch(egg, force=False)

    @responses.activate
    def test_fetch_unauthorized(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        url = "http://api.enthought.com/eggs/yoyo/"

        repository = Repository()

        path = os.path.join(_EGGINST_COMMON_DATA, filename)
        package = RepositoryPackageMetadata.from_egg(path, url)
        repository.add_package(package)

        responses.add(responses.GET, url + filename,
                      body='{"error": "forbidden"}',
                      status=403)
        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)

        # When/Then
        with self.assertRaises(requests.exceptions.HTTPError):
            downloader.fetch(filename)
