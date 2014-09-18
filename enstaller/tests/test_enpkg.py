import os.path
import shutil
import sys
import tempfile

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from egginst.main import EggInst
from egginst.tests.common import mkdtemp, DUMMY_EGG, _EGGINST_COMMON_DATA
from egginst.utils import compute_md5, makedirs

from enstaller.config import Configuration
from enstaller.enpkg import Enpkg, FetchAction, InstallAction, RemoveAction
from enstaller.errors import EnpkgError
from enstaller.fetch import DownloadManager, URLFetcher
from enstaller.repository import (egg_name_to_name_version,
                                  PackageMetadata, Repository,
                                  RepositoryPackageMetadata)
from enstaller.utils import PY_VER, path_to_uri
from enstaller.vendor import responses

from .common import (dummy_repository_package_factory,
                     mock_history_get_state_context, repository_factory)


def _unconnected_enpkg_factory():
    """
    Create an Enpkg instance which does not require an authenticated
    repository.
    """
    config = Configuration()
    repository = Repository()
    mocked_fetcher = mock.Mock()
    mocked_fetcher.cache_directory = config.repository_cache
    return Enpkg(repository, mocked_fetcher)

class TestEnpkgActions(unittest.TestCase):
    def test_empty_actions(self):
        """
        Ensuring enpkg.execute([]) does not crash
        """
        # Given
        enpkg = _unconnected_enpkg_factory()

        # When/Then
        enpkg.execute([])

    def test_remove(self):
        repository = Repository()

        with mkdtemp() as d:
            makedirs(d)

            for egg in [DUMMY_EGG]:
                egginst = EggInst(egg, d)
                egginst.install()

            enpkg = Enpkg(repository, mock.Mock(), prefixes=[d])

            with mock.patch("enstaller.enpkg.RemoveAction.execute") as mocked_remove:
                actions = enpkg._solver.remove_actions("dummy")
                enpkg.execute(actions)
                self.assertTrue(mocked_remove.called)

class TestEnpkgExecute(unittest.TestCase):
    def setUp(self):
        self.prefixes = [tempfile.mkdtemp()]

    def tearDown(self):
        for prefix in self.prefixes:
            shutil.rmtree(prefix)

    def test_simple_fetch(self):
        egg = "yoyo.egg"
        fetch_opcode = 0

        repository = Repository()

        with mock.patch("enstaller.enpkg.FetchAction") as mocked_fetch:
            enpkg = Enpkg(repository, mock.Mock(), prefixes=self.prefixes)
            enpkg.ec = mock.MagicMock()
            enpkg.execute([("fetch_{0}".format(fetch_opcode), egg)])

            self.assertTrue(mocked_fetch.called)
            mocked_fetch.assert_called()

    def test_simple_install(self):
        config = Configuration()

        egg = DUMMY_EGG
        base_egg = os.path.basename(egg)
        fetch_opcode = 0

        entries = [
            dummy_repository_package_factory("dummy", "1.0.1", 1)
        ]

        repository = repository_factory(entries)

        with mock.patch("enstaller.enpkg.FetchAction.execute") as mocked_fetch:
            with mock.patch("enstaller.enpkg.InstallAction.execute") as mocked_install:
                mocked_fetcher = mock.Mock()
                mocked_fetcher.cache_directory = config.repository_cache
                enpkg = Enpkg(repository, mocked_fetcher,
                              prefixes=self.prefixes)
                actions = enpkg._solver.install_actions("dummy")
                enpkg.execute(actions)

                mocked_fetch.assert_called()
                mocked_install.assert_called_with()


class TestEnpkgRevert(unittest.TestCase):
    def setUp(self):
        self.prefixes = [tempfile.mkdtemp()]

    def tearDown(self):
        for prefix in self.prefixes:
            shutil.rmtree(prefix)

    def test_empty_history(self):
        repository = Repository()

        enpkg = Enpkg(repository, mock.Mock(), prefixes=self.prefixes)
        enpkg.revert_actions(0)

        with self.assertRaises(EnpkgError):
            enpkg.revert_actions(1)

    def test_invalid_argument(self):
        repository = Repository()

        enpkg = Enpkg(repository, mock.Mock(), prefixes=self.prefixes)
        with self.assertRaises(EnpkgError):
            enpkg.revert_actions([])

    def test_revert_missing_unavailable_egg(self):
        egg = "non_existing_dummy_egg-1.0.0-1.egg"
        enpkg = _unconnected_enpkg_factory()
        with self.assertRaises(EnpkgError):
            enpkg.revert_actions(set([egg]))

    @responses.activate
    def test_simple_scenario(self):
        egg = DUMMY_EGG
        r_actions = {1: [], 0: [("remove", os.path.basename(egg))]}
        config = Configuration()

        repository = Repository()
        package = RepositoryPackageMetadata.from_egg(egg)
        package.python = PY_VER
        repository.add_package(package)

        with open(egg, "rb") as fp:
            responses.add(responses.GET, package.source_url,
                         body=fp.read(), status=200,
                         content_type='application/json')

        downloader = DownloadManager(URLFetcher(config.repository_cache), repository)

        enpkg = Enpkg(repository, downloader, prefixes=self.prefixes)
        actions = enpkg._solver.install_actions("dummy")
        enpkg.execute(actions)

        name, version = egg_name_to_name_version(egg)
        enpkg._installed_repository.find_package(name, version)

        for state in [0, 1]:
            actions = enpkg.revert_actions(state)
            self.assertEqual(actions, r_actions[state])

    def test_enstaller_not_removed(self):
        enstaller_egg = set(["enstaller-4.6.2-1.egg"])
        installed_eggs = set(["dummy-1.0.0-1.egg", "another_dummy-1.0.0-1.egg"])

        with mock_history_get_state_context(installed_eggs | enstaller_egg):
            enpkg = _unconnected_enpkg_factory()
            ret = enpkg.revert_actions(installed_eggs)

            self.assertEqual(ret, [])

    def test_same_state(self):
        installed_eggs = ["dummy-1.0.0-1.egg", "another_dummy-1.0.0-1.egg"]

        with mock_history_get_state_context(installed_eggs):
            enpkg = _unconnected_enpkg_factory()
            ret = enpkg.revert_actions(set(installed_eggs))

            self.assertEqual(ret, [])

    def test_superset(self):
        """
        Ensure installed eggs not in current state are removed.
        """
        installed_eggs = ["dummy-1.0.0-1.egg", "another_dummy-1.0.0-1.egg"]

        with mock_history_get_state_context(installed_eggs):
            enpkg = _unconnected_enpkg_factory()
            ret = enpkg.revert_actions(set(installed_eggs[:1]))

            self.assertEqual(ret, [("remove", "another_dummy-1.0.0-1.egg")])

    def test_subset(self):
        r_actions = [("fetch_0", "another_dummy-1.0.0-1.egg"),
                     ("install", "another_dummy-1.0.0-1.egg")]

        installed_eggs = ["dummy-1.0.0-1.egg"]
        revert_eggs = ["dummy-1.0.0-1.egg", "another_dummy-1.0.0-1.egg"]

        with mock_history_get_state_context(installed_eggs):
            enpkg = _unconnected_enpkg_factory()
            with mock.patch.object(enpkg, "_remote_repository"):
                ret = enpkg.revert_actions(set(revert_eggs))
                self.assertEqual(ret, r_actions)


class TestFetchAction(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _downloader_factory(self, paths):
        repository = Repository()
        for path in paths:
            package = RepositoryPackageMetadata.from_egg(path)
            repository.add_package(package)

        return DownloadManager(URLFetcher(self.tempdir), repository), repository

    def _add_response_for_path(self, path):
        with open(path, "rb") as fp:
            responses.add(responses.GET, path_to_uri(path),
                         body=fp.read(), status=200,
                         content_type='application/octet-stream')

    @responses.activate
    def test_simple(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)
        downloader, repository = self._downloader_factory([path])
        self._add_response_for_path(path)

        # When
        action = FetchAction(path, downloader, repository)
        action.execute()

        # Then
        target = os.path.join(downloader.cache_directory, filename)
        self.assertTrue(os.path.exists(target))
        self.assertEqual(compute_md5(target), compute_md5(path))
        self.assertFalse(action.is_canceled)

    @responses.activate
    def test_iteration(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)
        downloader, repository = self._downloader_factory([path])
        self._add_response_for_path(path)

        # When
        action = FetchAction(path, downloader, repository)
        for step in action:
            pass

        # Then
        target = os.path.join(downloader.cache_directory, filename)
        self.assertTrue(os.path.exists(target))
        self.assertEqual(compute_md5(target), compute_md5(path))
        self.assertFalse(action.is_canceled)

    @responses.activate
    def test_iteration_cancel(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)
        downloader, repository = self._downloader_factory([path])
        self._add_response_for_path(path)

        # When
        action = FetchAction(path, downloader, repository)
        for step in action:
            action.cancel()

        # Then
        target = os.path.join(downloader.cache_directory, filename)
        self.assertFalse(os.path.exists(target))
        self.assertTrue(action.is_canceled)

    @responses.activate
    def test_progress_manager_iter(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)
        downloader, repository = self._downloader_factory([path])
        self._add_response_for_path(path)

        # When/Then
        class MyDummyProgressBar(object):
            def update(self, n):
                self.fail("progress bar called")
            def __enter__(self):
                return self
            def __exit__(self, *a, **kw):
                pass

        progress = MyDummyProgressBar()
        action = FetchAction(path, downloader, repository,
                             progress_bar_factory=lambda *a, **kw: progress)
        for step in action:
            pass


    @responses.activate
    def test_progress_manager(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)
        downloader, repository = self._downloader_factory([path])
        self._add_response_for_path(path)

        class MyDummyProgressBar(object):
            def __init__(self):
                self.called = False
            def update(self, n):
                self.called = True
            def __enter__(self):
                return self
            def __exit__(self, *a, **kw):
                pass

        progress = MyDummyProgressBar()
        action = FetchAction(path, downloader, repository,
                             progress_bar_factory=lambda *a, **kw: progress)
        action.execute()

        # Then
        self.assertTrue(progress.called)


class TestRemoveAction(unittest.TestCase):
    def setUp(self):
        self.top_prefix = tempfile.mkdtemp()
        self.top_installed_repository = Repository(self.top_prefix)
        self.installed_repository = Repository(self.top_prefix)

    def tearDown(self):
        shutil.rmtree(self.top_prefix)

    def _install_eggs(self, paths):
        repository = Repository()
        for path in paths:
            package = RepositoryPackageMetadata.from_egg(path)
            repository.add_package(package)

        for path in paths:
            action = InstallAction(path, self.top_prefix, repository,
                                   self.top_installed_repository,
                                   self.installed_repository,
                                   os.path.dirname(path))
            action.execute()

    def test_simple(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)

        metadata = PackageMetadata.from_egg(path)

        self._install_eggs([path])

        # When
        action = RemoveAction(path, self.top_prefix,
                              self.top_installed_repository,
                              self.installed_repository)
        action.execute()

        # Then
        repository = Repository._from_prefixes([self.top_prefix])
        self.assertFalse(repository.has_package(metadata))
        self.assertFalse(self.top_installed_repository.has_package(metadata))
        self.assertFalse(self.installed_repository.has_package(metadata))
        self.assertFalse(action.is_canceled)

    def test_iteration(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)

        metadata = PackageMetadata.from_egg(path)

        self._install_eggs([path])


        # When
        action = RemoveAction(path, self.top_prefix,
                              self.top_installed_repository,
                              self.installed_repository)
        for step in action:
            pass

        # Then
        repository = Repository._from_prefixes([self.top_prefix])
        self.assertFalse(repository.has_package(metadata))
        self.assertFalse(self.top_installed_repository.has_package(metadata))
        self.assertFalse(self.installed_repository.has_package(metadata))
        self.assertFalse(action.is_canceled)


    def test_iteration_cancel(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)

        metadata = PackageMetadata.from_egg(path)

        self._install_eggs([path])


        # When
        action = RemoveAction(path, self.top_prefix,
                              self.top_installed_repository,
                              self.installed_repository)
        for step in action:
            action.cancel()

        # Then
        repository = Repository._from_prefixes([self.top_prefix])
        self.assertFalse(repository.has_package(metadata))
        self.assertFalse(self.top_installed_repository.has_package(metadata))
        self.assertFalse(self.installed_repository.has_package(metadata))

        self.assertTrue(action.is_canceled)
