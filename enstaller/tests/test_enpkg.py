import os.path
import shutil
import sys
import tempfile
import threading
import time

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from egginst.main import EggInst
from egginst.tests.common import mkdtemp, DUMMY_EGG
from egginst.utils import makedirs

from enstaller.config import Configuration
from enstaller.enpkg import Enpkg
from enstaller.errors import EnpkgError
from enstaller.fetch import DownloadManager
from enstaller.repository import (egg_name_to_name_version, PackageMetadata,
                                  Repository, RepositoryPackageMetadata)
from enstaller.utils import PY_VER

from .common import (dummy_repository_package_factory,
                     mock_history_get_state_context, mock_url_fetcher,
                     repository_factory)


class TestEnpkg(unittest.TestCase):
    def test_query_simple_with_local(self):
        """
        Ensure enpkg.query finds both local and remote eggs.
        """
        local_egg = DUMMY_EGG

        entries = [
            dummy_repository_package_factory("dummy", "1.6.1", 1),
            dummy_repository_package_factory("dummy", "1.8k", 2),
        ]

        repository = repository_factory(entries)

        local_entry = PackageMetadata.from_egg(DUMMY_EGG)

        with mkdtemp() as d:
            prefixes = [d]
            enpkg = Enpkg(repository, mock.Mock(), prefixes=prefixes)
            enpkg._install_egg(local_egg)

            remote_and_local_repository = Repository._from_prefixes(prefixes)
            for package in repository.iter_packages():
                remote_and_local_repository.add_package(package)
            packages = remote_and_local_repository.find_packages("dummy")
            self.assertItemsEqual([p.key for p in packages],
                                  [entry.key for entry in entries + [local_entry]])

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

            with mock.patch("enstaller.enpkg.EggInst.remove") as mocked_remove:
                actions = enpkg._solver.remove_actions("dummy")
                enpkg.execute(actions)
                self.assertTrue(mocked_remove.called)

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

        with mock.patch("enstaller.enpkg.Enpkg._fetch"):
            with mock.patch("enstaller.enpkg.Enpkg._install_egg", fake_install):
                enpkg = Enpkg(repository, mock.Mock())
                actions = enpkg._solver.install_actions("numpy")

                t = threading.Thread(target=lambda: enpkg.execute(actions))
                t.start()

                enpkg.abort_execution()
                t.join(timeout=10)

        self.assertEqual(sentinel, [])

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

        with mock.patch("enstaller.enpkg.Enpkg._fetch") as mocked_fetch:
            enpkg = Enpkg(repository, mock.Mock(), prefixes=self.prefixes)
            enpkg.ec = mock.MagicMock()
            enpkg.execute([("fetch_{0}".format(fetch_opcode), egg)])

            self.assertTrue(mocked_fetch.called)
            mocked_fetch.assert_called_with(egg, force=fetch_opcode)

    def test_simple_install(self):
        config = Configuration()

        egg = DUMMY_EGG
        base_egg = os.path.basename(egg)
        fetch_opcode = 0

        entries = [
            dummy_repository_package_factory("dummy", "1.0.1", 1)
        ]

        repository = repository_factory(entries)

        with mock.patch("enstaller.enpkg.Enpkg._fetch") as mocked_fetch:
            with mock.patch("enstaller.enpkg.Enpkg._install_egg") as mocked_install:
                mocked_fetcher = mock.Mock()
                mocked_fetcher.cache_directory = config.repository_cache
                enpkg = Enpkg(repository, mocked_fetcher,
                              prefixes=self.prefixes)
                actions = enpkg._solver.install_actions("dummy")
                enpkg.execute(actions)

                mocked_fetch.assert_called_with(base_egg, force=fetch_opcode)
                mocked_install.assert_called_with(
                    os.path.join(config.repository_cache, base_egg),
                    entries[0].s3index_data)

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

    def test_simple_scenario(self):
        egg = DUMMY_EGG
        r_actions = {1: [], 0: [("remove", os.path.basename(egg))]}
        config = Configuration()

        repository = Repository()
        package = RepositoryPackageMetadata.from_egg(egg)
        package.python = PY_VER
        repository.add_package(package)
        downloader = DownloadManager(repository, config.repository_cache)

        with mock_url_fetcher(downloader, open(egg)):
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
