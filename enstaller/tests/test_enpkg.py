import os.path
import shutil
import sys
import tempfile
import threading
import time

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from egginst.main import EggInst
from egginst.tests.common import mkdtemp, DUMMY_EGG, NOSE_1_2_1, NOSE_1_3_0
from egginst.utils import makedirs

from enstaller.config import Configuration
from enstaller.egg_meta import split_eggname
from enstaller.enpkg import Enpkg
from enstaller.enpkg import get_writable_local_dir
from enstaller.errors import EnpkgError, NoPackageFound
from enstaller.fetch import DownloadManager
from enstaller.main import _create_enstaller_update_enpkg
from enstaller.repository import (egg_name_to_name_version, PackageMetadata,
                                  Repository)
from enstaller.store.indexed import LocalIndexedStore, RemoteHTTPIndexedStore
from enstaller.store.tests.common import EggsStore

from .common import (dummy_repository_package_factory,
                     mock_history_get_state_context, mock_url_fetcher,
                     repository_factory)


class TestMisc(unittest.TestCase):
    def test_writable_local_dir_writable(self):
        config = Configuration()
        with mkdtemp() as d:
            config.repository_cache = d
            self.assertEqual(get_writable_local_dir(config), d)

    def test_writable_local_dir_non_writable(self):
        fake_dir = "/some/dummy_dir/hopefully/doesnt/exists"

        config = Configuration()
        config.repository_cache = fake_dir
        def mocked_makedirs(d):
            raise OSError("mocked makedirs")
        with mock.patch("os.makedirs", mocked_makedirs):
            self.assertNotEqual(get_writable_local_dir(config), "/foo")


class TestEnstallerUpdateHack(unittest.TestCase):
    def test_scenario1(self):
        """Test that we upgrade when remote is more recent than local."""
        remote_versions = [("4.6.1", 1)]
        local_version = "4.6.0"

        actions = self._compute_actions(remote_versions, local_version)
        self.assertNotEqual(actions, [])

    def test_scenario2(self):
        """Test that we don't upgrade when remote is less recent than local."""
        remote_versions = [("4.6.1", 1)]
        local_version = "4.6.2"

        actions = self._compute_actions(remote_versions, local_version)
        self.assertEqual(actions, [])

    def _compute_actions(self, remote_versions, local_version):
        prefixes = [sys.prefix]

        entries = [dummy_repository_package_factory("enstaller", version,
                                                    build)
                   for version, build in remote_versions]
        repository = repository_factory(entries)

        enpkg = Enpkg(repository, mock.Mock(), prefixes=prefixes,
                      config=Configuration())
        new_enpkg = _create_enstaller_update_enpkg(enpkg, local_version)
        return new_enpkg._install_actions_enstaller(local_version)


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
            enpkg = Enpkg(repository, mock.Mock(), prefixes=prefixes,
                          config=Configuration())
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
    repository = Repository()
    return Enpkg(repository, mock.Mock(), config=Configuration())

class TestEnpkgActions(unittest.TestCase):
    def test_empty_actions(self):
        """
        Ensuring enpkg.execute([]) does not crash
        """
        # Given
        enpkg = _unconnected_enpkg_factory()

        # When/Then
        enpkg.execute([])

    def test_install_simple(self):
        entries = [
            dummy_repository_package_factory("numpy", "1.6.1", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
            dummy_repository_package_factory("numpy", "1.7.1", 2),
        ]

        r_actions = [
            ('fetch_0', 'numpy-1.8.0-2.egg'),
            ('install', 'numpy-1.8.0-2.egg')
        ]

        repository = repository_factory(entries)

        with mkdtemp() as d:
            enpkg = Enpkg(repository, mock.Mock(), prefixes=[d],
                          config=Configuration())
            actions = enpkg.install_actions("numpy")

            self.assertEqual(actions, r_actions)

    def test_install_no_egg_entry(self):
        entries = [
            dummy_repository_package_factory("numpy", "1.6.1", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
        ]

        repository = repository_factory(entries)

        with mkdtemp() as d:
            enpkg = Enpkg(repository, mock.Mock(), prefixes=[d],
                          config=Configuration())
            with self.assertRaises(NoPackageFound):
                enpkg.install_actions("scipy")

    def test_remove_actions(self):
        repository = Repository()

        with mkdtemp() as d:
            makedirs(d)

            for egg in [DUMMY_EGG]:
                egginst = EggInst(egg, d)
                egginst.install()

            enpkg = Enpkg(repository, mock.Mock(), prefixes=[d],
                          config=Configuration())

            actions = enpkg.remove_actions("dummy")
            self.assertEqual(actions, [("remove", os.path.basename(DUMMY_EGG))])

    def test_remove(self):
        repository = Repository()

        with mkdtemp() as d:
            makedirs(d)

            for egg in [DUMMY_EGG]:
                egginst = EggInst(egg, d)
                egginst.install()

            enpkg = Enpkg(repository, mock.Mock(), prefixes=[d],
                          config=Configuration())

            with mock.patch("enstaller.enpkg.EggInst.remove") as mocked_remove:
                actions = enpkg.remove_actions("dummy")
                enpkg.execute(actions)
                self.assertTrue(mocked_remove.called)

    def test_remove_non_existing(self):
        entries = [
            dummy_repository_package_factory("numpy", "1.6.1", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
        ]

        repository = repository_factory(entries)

        with mkdtemp() as d:
            enpkg = Enpkg(repository, mock.Mock(), prefixes=[d],
                          config=Configuration())
            with self.assertRaises(EnpkgError):
                enpkg.remove_actions("numpy")

    def test_chained_override_update(self):
        """ Test update to package with latest version in lower prefix
        but an older version in primary prefix.
        """
        l0_egg = NOSE_1_3_0
        l1_egg = NOSE_1_2_1

        expected_actions = [
            ('fetch_0', os.path.basename(l0_egg)),
            ('remove', os.path.basename(l1_egg)),
            ('install', os.path.basename(l0_egg)),
        ]

        entries = [
            dummy_repository_package_factory(*split_eggname(os.path.basename(l0_egg))),
        ]

        repository = repository_factory(entries)

        with mkdtemp() as d:
            l0 = os.path.join(d, 'l0')
            l1 = os.path.join(d, 'l1')
            makedirs(l0)
            makedirs(l1)

            # Install latest version in l0
            EggInst(l0_egg, l0).install()
            # Install older version in l1
            EggInst(l1_egg, l1).install()

            repository = repository_factory(entries)
            enpkg = Enpkg(repository, mock.Mock(), prefixes=[l1, l0],
                          config=Configuration())

            actions = enpkg.install_actions("nose")
            self.assertListEqual(actions, expected_actions)

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

        config = Configuration()

        with mock.patch("enstaller.enpkg.Enpkg._fetch"):
            with mock.patch("enstaller.enpkg.Enpkg._install_egg", fake_install):
                enpkg = Enpkg(repository, mock.Mock(), config=config)
                actions = enpkg.install_actions("numpy")

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
            enpkg = Enpkg(repository, mock.Mock(), prefixes=self.prefixes,
                          config=Configuration())
            enpkg.ec = mock.MagicMock()
            enpkg.execute([("fetch_{0}".format(fetch_opcode), egg)])

            self.assertTrue(mocked_fetch.called)
            mocked_fetch.assert_called_with(egg, force=fetch_opcode)

    def test_simple_install(self):
        egg = DUMMY_EGG
        base_egg = os.path.basename(egg)
        fetch_opcode = 0

        entries = [
            dummy_repository_package_factory("dummy", "1.0.1", 1)
        ]

        repository = repository_factory(entries)

        with mock.patch("enstaller.enpkg.Enpkg._fetch") as mocked_fetch:
            with mock.patch("enstaller.enpkg.Enpkg._install_egg") as mocked_install:
                enpkg = Enpkg(repository, mock.Mock(), prefixes=self.prefixes,
                              config=Configuration())
                actions = enpkg.install_actions("dummy")
                enpkg.execute(actions)

                mocked_fetch.assert_called_with(base_egg, force=fetch_opcode)
                mocked_install.assert_called_with(os.path.join(enpkg.local_dir,
                                                               base_egg),
                                                  entries[0].s3index_data)

class TestEnpkgRevert(unittest.TestCase):
    def setUp(self):
        self.prefixes = [tempfile.mkdtemp()]

    def tearDown(self):
        for prefix in self.prefixes:
            shutil.rmtree(prefix)

    def test_empty_history(self):
        store = EggsStore([])
        store.connect()
        repository = Repository._from_store(store)

        enpkg = Enpkg(repository, mock.Mock(), prefixes=self.prefixes,
                      config=Configuration())
        enpkg.revert_actions(0)

        with self.assertRaises(EnpkgError):
            enpkg.revert_actions(1)

    def test_invalid_argument(self):
        repository = Repository()

        enpkg = Enpkg(repository, mock.Mock(), prefixes=self.prefixes,
                      config=Configuration())
        with self.assertRaises(EnpkgError):
            enpkg.revert_actions([])

    def test_simple_scenario(self):
        egg = DUMMY_EGG
        r_actions = {1: [], 0: [("remove", os.path.basename(egg))]}
        config = Configuration()

        store = EggsStore([egg])
        store.connect()
        repository = Repository._from_store(store)
        downloader = DownloadManager(repository, config.local)

        with mock_url_fetcher(downloader, open(egg)):
            enpkg = Enpkg(repository, downloader, prefixes=self.prefixes,
                          config=config)
            actions = enpkg.install_actions("dummy")
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
