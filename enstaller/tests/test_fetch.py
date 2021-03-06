import os
import os.path
import shutil
import sys
import tempfile

import requests
import responses

from egginst.tests.common import _EGGINST_COMMON_DATA

from enstaller.errors import InvalidChecksum
from enstaller.fetch import _DownloadManager
from enstaller.repository import Repository, RemotePackageMetadata
from enstaller.repository_info import CanopyRepositoryInfo
from enstaller.utils import compute_md5

from enstaller.tests.common import mocked_session_factory

if sys.version_info[0] == 2:
    import unittest2 as unittest
else:
    import unittest


class Test_DownloadManager(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _create_store_and_repository(self, eggs):
        repository = Repository()
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RemotePackageMetadata.from_egg(path)
            repository.add_package(package)

        return repository

    def test_fetch_simple(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        repository = self._create_store_and_repository([filename])
        package = repository.find_package("nose", "1.3.0-1")

        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        downloader.fetch(package)

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
        package = RemotePackageMetadata.from_egg(path)
        package._md5 = "a" * 32
        repository.add_package(package)

        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        with self.assertRaises(InvalidChecksum):
            downloader.fetch(package)

    def test_fetch_abort(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        repository = self._create_store_and_repository([filename])
        package = repository.find_package("nose", "1.3.0-1")

        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        target = os.path.join(self.tempdir, filename)

        # When
        context = downloader.iter_fetch(package)
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
        package = repository.find_package("nose", "1.3.0-1")

        # When
        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        downloader.fetch(package)

        # Then
        target = os.path.join(self.tempdir, egg)
        self.assertTrue(os.path.exists(target))

    def test_fetch_egg_refetch_invalid_md5(self):
        # Given
        egg = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, egg)

        repository = self._create_store_and_repository([egg])
        package = repository.find_package("nose", "1.3.0-1")

        def _corrupt_file(target):
            with open(target, "wb") as fo:
                fo.write(b"")

        # When
        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        downloader.fetch(package)

        # Then
        target = os.path.join(self.tempdir, egg)
        self.assertEqual(compute_md5(target), compute_md5(path))

        # When
        _corrupt_file(target)

        # Then
        self.assertNotEqual(compute_md5(target), compute_md5(path))

        # When
        downloader.fetch(package, force=True)

        # Then
        self.assertEqual(compute_md5(target), compute_md5(path))

        # When/Then
        # Ensure we deal correctly with force=False when the egg is already
        # there.
        downloader.fetch(package, force=False)

    @responses.activate
    def test_fetch_unauthorized(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        store_url = "http://api.enthought.com"
        repository_info = CanopyRepositoryInfo(store_url)

        repository = Repository()

        path = os.path.join(_EGGINST_COMMON_DATA, filename)
        package = RemotePackageMetadata.from_egg(path, repository_info)
        repository.add_package(package)

        responses.add(responses.GET, package.source_url,
                      body='{"error": "forbidden"}',
                      status=403)
        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)

        # When/Then
        with self.assertRaises(requests.exceptions.HTTPError):
            downloader.fetch(package)
