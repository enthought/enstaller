from __future__ import absolute_import

import re
import shutil
import tempfile
import textwrap
import unittest

from egginst.main import EggInst
from egginst.tests.common import DUMMY_EGG, mkdtemp

from enstaller.repository import Repository
from enstaller.tests.common import dummy_installed_package_factory, mock_print

from ..utils import (disp_store_info, install_time_string, name_egg,
                     print_installed)


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
            d = "/Users/cournape/tmp/egginst"
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
