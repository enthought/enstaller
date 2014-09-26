from __future__ import absolute_import

import re
import shutil
import sys
import tempfile
import textwrap

import mock

from egginst._compat import TestCase
from egginst.main import EggInst
from egginst.tests.common import DUMMY_EGG, mkdtemp

from enstaller.auth import UserInfo
from enstaller.config import Configuration
from enstaller.enpkg import Enpkg
from enstaller.repository import Repository
from enstaller.session import Session
from enstaller.tests.common import (DummyAuthenticator, FakeOptions,
                                    create_prefix_with_eggs,
                                    dummy_installed_package_factory,
                                    dummy_repository_package_factory,
                                    mocked_session_factory,
                                    mock_print)

from ..utils import (disp_store_info, install_req, install_time_string,
                     name_egg, print_installed, updates_check)

if sys.version_info < (2, 7):
    # FIXME: this looks quite fishy. On 2.6, with unittest2, the assertRaises
    # context manager does not contain the actual exception object ?
    def exception_code(ctx):
        return ctx.exception
else:
    def exception_code(ctx):
        return ctx.exception.code


class TestMisc(TestCase):
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


class TestInfoStrings(TestCase):
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


class TestUpdatesCheck(TestCase):
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


class TestInstallReq(TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_install_not_available(self):
        # Given
        config = Configuration()
        session = Session(DummyAuthenticator(), self.prefix)

        nose = dummy_repository_package_factory("nose", "1.3.0", 1)
        nose.available = False
        repository = Repository()
        repository.add_package(nose)

        enpkg = Enpkg(repository,
                      mocked_session_factory(config.repository_cache),
                      [self.prefix])
        enpkg.execute = mock.Mock()

        # When/Then
        with mock.patch("enstaller.config.subscription_message") as \
            subscription_message:
            with self.assertRaises(SystemExit) as e:
                install_req(enpkg, config, "nose", FakeOptions())
            subscription_message.assert_called()
            self.assertEqual(e.exception.code, 1)

    def test_simple_install(self):
        remote_entries = [
            dummy_repository_package_factory("nose", "1.3.0", 1)
        ]

        with mock.patch("enstaller.main.Enpkg.execute") as m:
            enpkg = create_prefix_with_eggs(Configuration(), self.prefix, [],
                    remote_entries)
            install_req(enpkg, Configuration(), "nose", FakeOptions())
            m.assert_called_with([('fetch', 'nose-1.3.0-1.egg'),
                                  ('install', 'nose-1.3.0-1.egg')])

    def test_simple_non_existing_requirement(self):
        config = Configuration()
        r_error_string = "No egg found for requirement 'nono_le_petit_robot'.\n"
        non_existing_requirement = "nono_le_petit_robot"

        with mock.patch("enstaller.main.Enpkg.execute") as mocked_execute:
            enpkg = create_prefix_with_eggs(config, self.prefix, [])
            with mock_print() as mocked_print:
                with self.assertRaises(SystemExit) as e:
                    install_req(enpkg, config, non_existing_requirement,
                                FakeOptions())
                self.assertEqual(exception_code(e), 1)
                self.assertEqual(mocked_print.value, r_error_string)
            mocked_execute.assert_not_called()

    def test_simple_no_install_needed(self):
        installed_entries = [
            dummy_installed_package_factory("nose", "1.3.0", 1)
        ]
        remote_entries = [
            dummy_repository_package_factory("nose", "1.3.0", 1)
        ]
        config = Configuration()

        with mock.patch("enstaller.main.Enpkg.execute") as m:
            enpkg = create_prefix_with_eggs(config, self.prefix,
                                             installed_entries, remote_entries)
            install_req(enpkg, config, "nose", FakeOptions())
            m.assert_called_with([])

    def test_recursive_install_unavailable_dependency(self):
        config = Configuration()
        session = Session(DummyAuthenticator(), self.prefix)

        auth = ("nono", "le gros robot")
        session.authenticate(auth)
        config.set_auth(*auth)

        r_output = textwrap.dedent("""
        Cannot install 'scipy', as this package (or some of its requirements) are not
        available at your subscription level 'Canopy / EPD Free' (You are currently
        logged in as 'nono').
        """)

        self.maxDiff = None
        numpy = dummy_repository_package_factory("numpy", "1.7.1", 1)
        numpy.available = False
        scipy = dummy_repository_package_factory("scipy", "0.12.0", 1)
        scipy.packages = ["numpy 1.7.1"]

        remote_entries = [numpy, scipy]

        with mock.patch("enstaller.main.Enpkg.execute"):
            enpkg = create_prefix_with_eggs(config, self.prefix, [], remote_entries)
            with mock_print() as m:
                with self.assertRaises(SystemExit):
                    install_req(enpkg, config, "scipy", FakeOptions())
                self.assertMultiLineEqual(m.value, r_output)
