from __future__ import absolute_import

import re
import shutil
import tempfile
import textwrap
import unittest

from egginst.main import EggInst
from egginst.tests.common import DUMMY_EGG, mkdtemp

from enstaller.repository import Repository
from enstaller.tests.common import (dummy_installed_package_factory,
                                    dummy_repository_package_factory,
                                    mock_print)

from ..utils import (disp_store_info, install_time_string, name_egg,
                     print_installed, updates_check)


class TestMisc(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_disp_store_info(self):
        info = {"store_location": "https://api.enthought.com/eggs/osx-64/"}
        self.assertEqual(disp_store_info(info), "api osx-64")

        info = {"store_location": "https://api.enthought.com/eggs/win-32/"}
        self.assertEqual(disp_store_info(info), "api win-32")

        info = {}
        self.assertEqual(disp_store_info(info), "-")

    def test_name_egg(self):
        name = "foo-1.0.0-1.egg"
        self.assertEqual(name_egg(name), "foo")

        name = "fu_bar-1.0.0-1.egg"
        self.assertEqual(name_egg(name), "fu_bar")

        with self.assertRaises(AssertionError):
            name = "some/dir/fu_bar-1.0.0-1.egg"
            name_egg(name)


class TestInfoStrings(unittest.TestCase):
    def test_print_install_time(self):
        with mkdtemp() as d:
            installed_entries = [dummy_installed_package_factory("dummy",
                                                                 "1.0.1", 1)]
            installed_repository = Repository()
            for package in installed_entries:
                installed_repository.add_package(package)

            self.assertRegexpMatches(install_time_string(installed_repository,
                                                         "dummy"),
                                     "dummy-1.0.1-1.egg was installed on:")

            self.assertEqual(install_time_string(installed_repository,
                                                 "ddummy"),
                             "")

    def test_print_installed(self):
        with mkdtemp() as d:
            r_out = textwrap.dedent("""\
                Name                 Version              Store
                ============================================================
                dummy                1.0.1-1              -
                """)
            ec = EggInst(DUMMY_EGG, d)
            ec.install()

            repository = Repository._from_prefixes([d])
            with mock_print() as m:
                print_installed(repository)
            self.assertMultiLineEqual(m.value, r_out)

            r_out = textwrap.dedent("""\
                Name                 Version              Store
                ============================================================
                """)

            repository = Repository._from_prefixes([d])
            with mock_print() as m:
                print_installed(repository, pat=re.compile("no_dummy"))
            self.assertEqual(m.value, r_out)


class TestUpdatesCheck(unittest.TestCase):
    def _create_repositories(self, entries, installed_entries):
        repository = Repository()
        for entry in entries:
            repository.add_package(entry)

        installed_repository = Repository()
        for entry in installed_entries:
            installed_repository.add_package(entry)

        return repository, installed_repository

    def test_update_check_new_available(self):
        # Given
        remote_entries = [
            dummy_repository_package_factory("dummy", "1.2.0", 1),
            dummy_repository_package_factory("dummy", "0.9.8", 1)
        ]
        installed_entries = [
                dummy_installed_package_factory("dummy", "1.0.1", 1)
        ]

        remote_repository, installed_repository = \
            self._create_repositories(remote_entries, installed_entries)

        # When
        updates, EPD_update =  updates_check(remote_repository,
                                             installed_repository)

        # Then
        self.assertEqual(EPD_update, [])
        self.assertEqual(len(updates), 1)
        update0 = updates[0]
        self.assertItemsEqual(update0.keys(), ["current", "update"])
        self.assertEqual(update0["current"]["version"], "1.0.1")
        self.assertEqual(update0["update"].version, "1.2.0")

    def test_update_check_no_new_available(self):
        # Given
        remote_entries = [
            dummy_repository_package_factory("dummy", "1.0.0", 1),
            dummy_repository_package_factory("dummy", "0.9.8", 1)
        ]
        installed_entries = [
                dummy_installed_package_factory("dummy", "1.0.1", 1)
        ]

        remote_repository, installed_repository = \
            self._create_repositories(remote_entries, installed_entries)


        # When
        updates, EPD_update =  updates_check(remote_repository,
                                             installed_repository)

        # Then
        self.assertEqual(EPD_update, [])
        self.assertEqual(updates, [])

    def test_update_check_no_available(self):
        # Given
        installed_entries = [
                dummy_installed_package_factory("dummy", "1.0.1", 1)
        ]

        remote_repository, installed_repository = \
            self._create_repositories([], installed_entries)


        # When
        updates, EPD_update =  updates_check(remote_repository,
                                             installed_repository)

        # Then
        self.assertEqual(EPD_update, [])
        self.assertEqual(updates, [])

    def test_update_check_epd(self):
        # Given
        remote_entries = [dummy_repository_package_factory("EPD", "7.3", 1)]
        installed_entries = [dummy_installed_package_factory("EPD", "7.2", 1)]

        remote_repository, installed_repository = \
            self._create_repositories(remote_entries, installed_entries)

        # When
        updates, EPD_update =  updates_check(remote_repository,
                                             installed_repository)

        # Then
        self.assertEqual(updates, [])
        self.assertEqual(len(EPD_update), 1)

        epd_update0 = EPD_update[0]
        self.assertItemsEqual(epd_update0.keys(), ["current", "update"])
        self.assertEqual(epd_update0["current"]["version"], "7.2")
        self.assertEqual(epd_update0["update"].version, "7.3")
