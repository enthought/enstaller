import os.path
import shutil
import sys
import tempfile

import mock
import responses

from egginst.main import _default_runtime_info
from egginst.progress import console_progress_manager_factory
from egginst.tests.common import mkdtemp, DUMMY_EGG, _EGGINST_COMMON_DATA
from egginst.utils import compute_md5, makedirs

from enstaller.config import Configuration
from enstaller.enpkg import Enpkg, FetchAction, InstallAction, RemoveAction
from enstaller.errors import EnpkgError, InvalidChecksum
from enstaller.fetch import _DownloadManager
from enstaller.package import (
    InstalledPackageMetadata, PackageMetadata, egg_name_to_name_version
)
from enstaller.repository import Repository, RemotePackageMetadata
from enstaller.repository_info import OldstyleRepositoryInfo
from enstaller.session import Session
from enstaller.utils import path_to_uri

from .common import (dummy_repository_package_factory,
                     mocked_session_factory,
                     mock_history_get_state_context, repository_factory,
                     unconnected_enpkg_factory, DummyAuthenticator)

if sys.version_info[0] == 2:
    import unittest2 as unittest
else:
    import unittest


class TestEnpkgActions(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_empty_actions(self):
        """
        Ensuring enpkg.execute([]) does not crash
        """
        # Given
        enpkg = unconnected_enpkg_factory()

        # When/Then
        enpkg.execute([])

    def test_remove(self):
        with mkdtemp() as d:
            makedirs(d)

            enpkg = unconnected_enpkg_factory([d])

            with mock.patch("enstaller.enpkg.RemoveAction.execute") as mocked_remove:
                actions = [("remove", DUMMY_EGG)]
                enpkg.execute(actions)
                self.assertTrue(mocked_remove.called)

    def _prepared_mocked_egginst(self, nfiles):
        installed_size = 1024 ** 2 * 2

        remover = mock.Mock()
        remover.installed_size = installed_size

        files = ["foo{0}".format(i) for i in range(nfiles)]
        remover.files = files
        remover.remove_iterator.return_value = iter(files)

        return remover

    @mock.patch("enstaller.enpkg.EggInst")
    def test_progress(self, EggInst):
        # Ensure the accumulated arg of updates is exactly the number of files
        # to be removed

        # Given
        nfiles = 245
        remover = self._prepared_mocked_egginst(nfiles)
        package = InstalledPackageMetadata.from_egg(DUMMY_EGG, "")

        EggInst.return_value._egginst_remover = remover
        top_repository = mock.Mock()
        remote_repository = mock.Mock()

        def factory(*a, **kw):
            return console_progress_manager_factory("fetching", *a, **kw)

        action = RemoveAction(package, self.prefix, top_repository,
                              remote_repository, factory)
        progress = mock.Mock()
        progress.__enter__ = mock.Mock(return_value=progress)
        progress.__exit__ = mock.Mock()

        # When
        with mock.patch("egginst.progress.ProgressBar", return_value=progress):
            for step in action.iter_execute():
                action.progress_update(step)

        # Then
        accumulated = sum(args[0] for args, kw in
                          progress.update.call_args_list)
        self.assertEqual(accumulated, nfiles)


class TestEnpkgExecute(unittest.TestCase):
    def setUp(self):
        self.prefixes = [tempfile.mkdtemp()]

    def tearDown(self):
        for prefix in self.prefixes:
            shutil.rmtree(prefix)

    def test_simple_fetch(self):
        egg = "yoyo.egg"
        fetch_opcode = 0

        with mock.patch("enstaller.enpkg.FetchAction") as mocked_fetch:
            enpkg = unconnected_enpkg_factory(prefixes=self.prefixes)
            enpkg.ec = mock.MagicMock()
            enpkg.execute([("fetch_{0}".format(fetch_opcode), egg)])

            self.assertTrue(mocked_fetch.called)
            self.assertTrue(mocked_fetch.called)

    def test_simple_install(self):
        config = Configuration()
        dummy_package = dummy_repository_package_factory("dummy", "1.0.1", 1)
        entries = [dummy_package]

        repository = repository_factory(entries)

        with mock.patch("enstaller.enpkg.FetchAction.execute") as mocked_fetch:
            with mock.patch("enstaller.enpkg.InstallAction.execute") as mocked_install:
                enpkg = Enpkg(repository,
                              mocked_session_factory(config.repository_cache),
                              prefixes=self.prefixes)
                actions = [
                    ("fetch", dummy_package),
                    ("install", dummy_package),
                ]
                enpkg.execute(actions)

                self.assertTrue(mocked_fetch.called)
                mocked_install.assert_called_with()


class TestEnpkgRevert(unittest.TestCase):
    def setUp(self):
        self.prefixes = [tempfile.mkdtemp()]

    def tearDown(self):
        for prefix in self.prefixes:
            shutil.rmtree(prefix)

    def test_empty_history(self):
        enpkg = unconnected_enpkg_factory(self.prefixes)
        enpkg.revert_actions(0)

        with self.assertRaises(EnpkgError):
            enpkg.revert_actions(1)

    def test_invalid_argument(self):
        repository = Repository()

        enpkg = Enpkg(repository,
                      mocked_session_factory(Configuration().repository_cache),
                      prefixes=self.prefixes)
        with self.assertRaises(EnpkgError):
            enpkg.revert_actions([])

    def test_revert_missing_unavailable_egg(self):
        egg = "non_existing_dummy_egg-1.0.0-1.egg"
        enpkg = Enpkg(Repository(),
                      mocked_session_factory(Configuration().repository_cache),
                      prefixes=self.prefixes)
        with self.assertRaises(EnpkgError):
            enpkg.revert_actions(set([egg]))

    @responses.activate
    def test_simple_scenario(self):
        egg = DUMMY_EGG
        r_actions = {1: [], 0: [("remove", os.path.basename(egg))]}
        config = Configuration()

        repository = Repository()
        package = RemotePackageMetadata.from_egg(egg)
        repository.add_package(package)

        with open(egg, "rb") as fp:
            responses.add(responses.GET, package.source_url,
                          body=fp.read(), status=200,
                          content_type='application/json')

        session = Session(DummyAuthenticator(), config.repository_cache)

        enpkg = Enpkg(repository, session, prefixes=self.prefixes)
        actions = [("fetch", package),
                   ("install", package)]
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
            enpkg = unconnected_enpkg_factory()
            ret = enpkg.revert_actions(installed_eggs)

            self.assertEqual(ret, [])

    def test_same_state(self):
        installed_eggs = ["dummy-1.0.0-1.egg", "another_dummy-1.0.0-1.egg"]

        with mock_history_get_state_context(installed_eggs):
            enpkg = unconnected_enpkg_factory()
            ret = enpkg.revert_actions(set(installed_eggs))

            self.assertEqual(ret, [])

    def test_superset(self):
        """
        Ensure installed eggs not in current state are removed.
        """
        installed_eggs = ["dummy-1.0.0-1.egg", "another_dummy-1.0.0-1.egg"]

        with mock_history_get_state_context(installed_eggs):
            enpkg = unconnected_enpkg_factory()
            ret = enpkg.revert_actions(set(installed_eggs[:1]))

            self.assertEqual(ret, [("remove", "another_dummy-1.0.0-1.egg")])

    def test_subset(self):
        r_actions = [("fetch_0", "another_dummy-1.0.0-1.egg"),
                     ("install", "another_dummy-1.0.0-1.egg")]

        installed_eggs = ["dummy-1.0.0-1.egg"]
        revert_eggs = ["dummy-1.0.0-1.egg", "another_dummy-1.0.0-1.egg"]

        with mock_history_get_state_context(installed_eggs):
            enpkg = unconnected_enpkg_factory()
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
            package = RemotePackageMetadata.from_egg(path)
            repository.add_package(package)

        return (_DownloadManager(Session(DummyAuthenticator(), self.tempdir), repository),
                repository)

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
        package = repository.find_package("nose", "1.3.0-1")
        self._add_response_for_path(path)

        # When
        action = FetchAction(package, downloader, repository)
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
        package = repository.find_package("nose", "1.3.0-1")
        self._add_response_for_path(path)

        # When
        action = FetchAction(package, downloader, repository)
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
        package = repository.find_package("nose", "1.3.0-1")
        self._add_response_for_path(path)

        # When
        action = FetchAction(package, downloader, repository)
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
        package = repository.find_package("nose", "1.3.0-1")
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
        action = FetchAction(package, downloader, repository,
                             progress_bar_factory=lambda *a, **kw: progress)
        for step in action:
            pass

    @responses.activate
    def test_progress_manager(self):
        # Given
        filename = "nose-1.3.0-1.egg"
        path = os.path.join(_EGGINST_COMMON_DATA, filename)
        downloader, repository = self._downloader_factory([path])
        package = repository.find_package("nose", "1.3.0-1")
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
        action = FetchAction(package, downloader, repository,
                             progress_bar_factory=lambda *a, **kw: progress)
        action.execute()

        # Then
        self.assertTrue(progress.called)

    def _add_failing_checksum_response(self, url, payload, n_invalid=2):
        counter = [0]

        def request_callback(request):
            counter[0] += 1

            headers = {}

            if counter[0] > n_invalid:
                return (200, headers, payload)
            else:
                return (200, headers, b"")

        responses.add_callback(responses.GET, url,
                               callback=request_callback,
                               content_type='application/octet-stream')

    def _retry_common_setup(self):
        store_url = "http://acme.com"
        repository_info = OldstyleRepositoryInfo(store_url)
        filename = "nose-1.3.0-1.egg"

        path = os.path.join(_EGGINST_COMMON_DATA, filename)

        repository = Repository()
        package = RemotePackageMetadata.from_egg(path, repository_info)
        repository.add_package(package)

        downloader = _DownloadManager(mocked_session_factory(self.tempdir),
                                      repository)
        return path, downloader, repository

    @responses.activate
    def test_not_enough_retry(self):
        # Given
        path, downloader, repository = self._retry_common_setup()
        package = repository.find_package("nose", "1.3.0-1")

        url = list(repository.iter_packages())[0].source_url
        with open(path, "rb") as fp:
            payload = fp.read()

        max_retries = 2
        self._add_failing_checksum_response(url, payload, max_retries)

        # When/Then
        action = FetchAction(package, downloader, repository,
                             max_retries=max_retries-1)
        with self.assertRaises(InvalidChecksum):
            action.execute()

    @responses.activate
    def test_retry(self):
        # Given
        path, downloader, repository = self._retry_common_setup()
        package = repository.find_package("nose", "1.3.0-1")

        url = "http://acme.com/{0}".format(os.path.basename(path))
        with open(path, "rb") as fp:
            payload = fp.read()

        max_retries = 4
        self._add_failing_checksum_response(url, payload, max_retries)

        # When/Then
        action = FetchAction(package, downloader, repository,
                             max_retries=max_retries)
        # No exception
        action.execute()


class TestRemoveAction(unittest.TestCase):
    def setUp(self):
        self.top_prefix = tempfile.mkdtemp()
        self.top_installed_repository = Repository()
        self.installed_repository = Repository()

        self.runtime_info = _default_runtime_info(self.top_prefix)

    def tearDown(self):
        shutil.rmtree(self.top_prefix)

    def _install_eggs(self, paths):
        repository = Repository()
        for path in paths:
            package = RemotePackageMetadata.from_egg(path)
            repository.add_package(package)

        for path in paths:
            action = InstallAction(package, self.runtime_info, repository,
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
        action = RemoveAction(metadata, self.runtime_info,
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
        action = RemoveAction(metadata, self.runtime_info,
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
        action = RemoveAction(metadata, self.runtime_info,
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
