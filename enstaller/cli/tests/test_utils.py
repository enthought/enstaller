from __future__ import absolute_import

import re
import shutil
import sys
import tempfile
import textwrap
import zlib

import mock

from egginst._compat import assertCountEqual
from egginst.main import EggInst
from egginst.tests.common import DUMMY_EGG, mkdtemp
from egginst.vendor.six.moves import unittest

from enstaller.config import Configuration
from enstaller.enpkg import Enpkg
from enstaller.repository import Repository
from enstaller.session import Session
from enstaller.tests.common import (DummyAuthenticator, FakeOptions,
                                    create_prefix_with_eggs,
                                    dummy_installed_package_factory,
                                    dummy_repository_package_factory,
                                    mocked_session_factory,
                                    mock_index, mock_print, mock_raw_input,
                                    PY_VER)
from enstaller.vendor import requests, responses
from enstaller.versions.enpkg import EnpkgVersion

from ..utils import (disp_store_info, exit_if_root_on_non_owned, install_req,
                     install_time_string, name_egg, print_installed,
                     repository_factory, updates_check)
from ..utils import _fetch_json_with_progress, _print_warning


if sys.version_info < (2, 7):
    # FIXME: this looks quite fishy. On 2.6, with unittest2, the assertRaises
    # context manager does not contain the actual exception object ?
    def exception_code(ctx):
        return ctx.exception
else:
    def exception_code(ctx):
        return ctx.exception.code


FAKE_AUTH = ("nono", "le gros robot")
V = EnpkgVersion.from_string


class TestExitIfRootOnNonOwned(unittest.TestCase):
    @mock.patch("enstaller.cli.utils.sys.platform", "win32")
    def test_windows(self):
        exit_if_root_on_non_owned()

    @unittest.skipIf(sys.platform == "win32", "no getuid on windows")
    @mock.patch("enstaller.cli.utils.sys.platform", "linux")
    @mock.patch("os.getuid", lambda: 0)
    def test_sudo(self):
        with mock.patch("enstaller.cli.utils.is_running_on_non_owned_python",
                        return_value=False):
            exit_if_root_on_non_owned()

        with mock.patch("enstaller.cli.utils.is_running_on_non_owned_python",
                        return_value=True):
            with mock_raw_input(""):
                with self.assertRaises(SystemExit):
                    exit_if_root_on_non_owned()

            with mock_raw_input("yes"):
                exit_if_root_on_non_owned()


class TestMisc(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test__print_warning(self):
        # Given
        message = "fail to crash"
        r_output = "Warning: fail to crash\n\n"

        # When
        with mock_print() as m:
            _print_warning(message)

        # Then
        self.assertMultiLineEqual(m.value, r_output)

    def test_disp_store_info(self):
        store_location = "https://api.enthought.com/eggs/osx-64/"
        self.assertEqual(disp_store_info(store_location), "api osx-64")

        store_location = "https://api.enthought.com/eggs/win-32/"
        self.assertEqual(disp_store_info(store_location), "api win-32")

        self.assertEqual(disp_store_info(""), "-")

    def test_name_egg(self):
        name = "foo-1.0.0-1.egg"
        self.assertEqual(name_egg(name), "foo")

        name = "fu_bar-1.0.0-1.egg"
        self.assertEqual(name_egg(name), "fu_bar")

        with self.assertRaises(AssertionError):
            name = "some/dir/fu_bar-1.0.0-1.egg"
            name_egg(name)

    @responses.activate
    def test_repository_factory(self):
        self.maxDiff = None

        # Given
        store_url = "https://acme.com"
        config = Configuration(store_url=store_url, use_webservice=False)
        config.set_repositories_from_names(["enthought/foo"])

        responses.add(responses.GET, config.indices[0][0],
                      status=404)

        session = mocked_session_factory(self.tempdir)
        r_warning = textwrap.dedent("""\
            Warning: Could not fetch the following indices:

                     - 'neko'

                     Those repositories do not exist (or you do not have the rights to
                     access them). You should edit your configuration to remove those
                     repositories.

        """)

        # When
        with mock_print() as m:
            with mock.patch("enstaller.cli.utils._display_store_name",
                            return_value="neko"):
                repository = repository_factory(session, config.indices)

        # Then
        self.assertEqual(len(list(repository.iter_packages())), 0)
        self.assertMultiLineEqual(m.value, r_warning)

        # When/Then
        with self.assertRaises(requests.exceptions.HTTPError):
            repository_factory(session, config.indices, raise_on_error=True)


class TestInfoStrings(unittest.TestCase):
    def test_print_install_time(self):
        with mkdtemp():
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
                dummy                1.0.1-1              {0}
                """.format(disp_store_info(d)))
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
        updates, EPD_update = updates_check(remote_repository,
                                            installed_repository)

        # Then
        self.assertEqual(EPD_update, [])
        self.assertEqual(len(updates), 1)
        update0 = updates[0]
        assertCountEqual(self, update0.keys(), ["current", "update"])
        self.assertEqual(update0["current"].version, V("1.0.1-1"))
        self.assertEqual(update0["update"].version, V("1.2.0-1"))

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
        updates, EPD_update = updates_check(remote_repository,
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
        updates, EPD_update = updates_check(remote_repository,
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
        updates, EPD_update = updates_check(remote_repository,
                                            installed_repository)

        # Then
        self.assertEqual(updates, [])
        self.assertEqual(len(EPD_update), 1)

        epd_update0 = EPD_update[0]
        assertCountEqual(self, epd_update0.keys(), ["current", "update"])
        self.assertEqual(epd_update0["current"].version, V("7.2-1"))
        self.assertEqual(epd_update0["update"].version, V("7.3-1"))


class TestInstallReq(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_install_not_available(self):
        # Given
        config = Configuration()
        config.update(auth=FAKE_AUTH)

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
        config.update(auth=auth)

        r_output = textwrap.dedent("""
        Cannot install 'scipy', as this package (or some of its requirements) are not
        available at your subscription level 'Canopy / EPD Free' (You are logged in as
        'nono').
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

    @mock_index({
        "rednose-0.2.3-1.egg": {
            "available": True,
            "build": 1,
            "md5": "41640f27172d248ccf6dcbfafe53ba4d",
            "mtime": 1300825734.0,
            "name": "rednose",
            "packages": [],
            "product": "pypi",
            "python": PY_VER,
            "size": 9227,
            "type": "egg",
            "version": "0.2.3"
        }
    })
    def test_install_pypi_requirement(self):
        self.maxDiff = None

        # Given
        r_message = textwrap.dedent("""\
        The following packages/requirements are coming from the PyPi repo:

        rednose

        The PyPi repository which contains >10,000 untested ("as is")
        packages. Some packages are licensed under GPL or other licenses
        which are prohibited for some users. Dependencies may not be
        provided. If you need an updated version or if the installation
        fails due to unmet dependencies, the Knowledge Base article
        Installing external packages into Canopy Python
        (https://support.enthought.com/entries/23389761) may help you with
        installing it.

        Are you sure that you wish to proceed?  (y/[n])
        """)

        config = Configuration()
        session = Session.from_configuration(config)
        session.authenticate(("nono", "le petit robot"))
        repository = repository_factory(session, config.indices)

        enpkg = Enpkg(repository, session, [self.prefix])
        enpkg.execute = mock.Mock()

        # When
        with mock_print() as mocked_print:
            with mock_raw_input("yes"):
                install_req(enpkg, config, "rednose", FakeOptions())

        # Then
        self.assertMultiLineEqual(mocked_print.value, r_message)

    @mock_index({
        "rednose-0.2.3-1.egg": {
            "available": True,
            "build": 1,
            "md5": "41640f27172d248ccf6dcbfafe53ba4d",
            "mtime": 1300825734.0,
            "name": "rednose",
            "packages": ["python_termstyle"],
            "product": "pypi",
            "python": PY_VER,
            "size": 9227,
            "type": "egg",
            "version": "0.2.3"
        }
    })
    def test_install_broken_pypi_requirement(self):
        self.maxDiff = None

        # Given
        r_message = textwrap.dedent("""
Broken pypi package 'rednose-0.2.3-1.egg': missing dependency 'python_termstyle'

Pypi packages are not officially supported. If this package is important to
you, please contact Enthought support to request its inclusion in our
officially supported repository.

In the mean time, you may want to try installing 'rednose-0.2.3-1.egg' from sources
with pip as follows:

    $ enpkg pip
    $ pip install <requested_package>

""")

        config = Configuration()
        session = Session.from_configuration(config)
        session.authenticate(("nono", "le petit robot"))
        repository = repository_factory(session, config.indices)

        enpkg = Enpkg(repository, session, [self.prefix])
        enpkg.execute = mock.Mock()

        # When
        with self.assertRaises(SystemExit):
            with mock_print() as mocked_print:
                with mock_raw_input("yes"):
                    install_req(enpkg, config, "rednose", FakeOptions())

        # Then
        self.assertMultiLineEqual(mocked_print.value, r_message)

    def _assert_ask_for_pypi(self, mocked_print):
        line = "The following packages/requirements are coming from the " \
               "PyPi repo:"
        self.assertTrue(mocked_print.value.startswith(line))

    def _assert_dont_ask_for_pypi(self, mocked_print):
        line = "The following packages/requirements are coming from the " \
               "PyPi repo:"
        self.assertFalse(mocked_print.value.startswith(line))

    @mock_index({
        "swig-2.0.2-1.egg": {
            "available": True,
            "build": 1,
            "md5": "41640f27172d248ccf6dcbfafe53ba4d",
            "mtime": 1300825734.0,
            "name": "swig",
            "packages": [],
            "product": "pypi",
            "python": PY_VER,
            "size": 9227,
            "type": "egg",
            "version": "2.0.2"
        },
        "swig-2.0.12-1.egg": {
            "available": True,
            "build": 1,
            "md5": "41640f27172d248ccf6dcbfafe53ba4d",
            "mtime": 1300825734.0,
            "name": "swig",
            "packages": [],
            "product": "free",
            "python": PY_VER,
            "size": 9227,
            "type": "egg",
            "version": "2.0.12"
        }
    })
    def test_install_non_pypi_after_pypi(self):
        # Given
        config = Configuration()
        config.update(auth=("nono", "le petit robot"))

        session = Session.from_configuration(config)
        session.authenticate(config.auth)

        repository = repository_factory(session, config.indices)

        enpkg = Enpkg(repository, session, [self.prefix])
        enpkg.execute = mock.Mock()

        # When
        with mock_print() as mocked_print:
            with mock_raw_input("yes"):
                install_req(enpkg, config, "swig", FakeOptions())

        # Then
        self._assert_dont_ask_for_pypi(mocked_print)

    @mock_index({
        "swig-2.0.2-1.egg": {
            "available": True,
            "build": 1,
            "md5": "41640f27172d248ccf6dcbfafe53ba4d",
            "mtime": 1300825734.0,
            "name": "swig",
            "packages": [],
            "product": "pypi",
            "python": PY_VER,
            "size": 9227,
            "type": "egg",
            "version": "2.0.2"
        },
        "swig-2.0.12-1.egg": {
            "available": True,
            "build": 1,
            "md5": "41640f27172d248ccf6dcbfafe53ba4d",
            "mtime": 1300825734.0,
            "name": "swig",
            "packages": [],
            "product": "free",
            "python": PY_VER,
            "size": 9227,
            "type": "egg",
            "version": "2.0.12"
        }
    })
    def test_install_pypi_before_non_pypi(self):
        # Given
        config = Configuration()
        config.update(auth=("nono", "le petit robot"))

        session = Session.from_configuration(config)
        session.authenticate(config.auth)

        repository = repository_factory(session, config.indices)

        enpkg = Enpkg(repository, session, [self.prefix])
        enpkg.execute = mock.Mock()

        # When
        with mock_print() as mocked_print:
            with mock_raw_input("yes"):
                install_req(enpkg, config, "swig 2.0.2", FakeOptions())

        # Then
        self._assert_ask_for_pypi(mocked_print)

        # When
        with mock_print() as mocked_print:
            with mock_raw_input("yes"):
                install_req(enpkg, config, "swig 2.0.2-1", FakeOptions())

        # Then
        self._assert_ask_for_pypi(mocked_print)


class TestFetchJsonWithProgress(unittest.TestCase):
    def _gzip_compress(self, data):
        compressor = zlib.compressobj(6, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
        body = compressor.compress(data)
        body += compressor.flush()
        return body

    @responses.activate
    def test_simple(self):

        # Given
        def callback(request):
            self.assertTrue("gzip" in
                            request.headers.get("Accept-Encoding", ""))

            headers = {"Content-Encoding": "gzip"}
            body = self._gzip_compress(b"{}")
            return (200, headers, body)

        responses.add_callback(responses.GET, "https://acme.com/index.json", callback)

        config = Configuration()

        # When
        session = Session.from_configuration(config)
        resp = session.fetch("https://acme.com/index.json")
        data = _fetch_json_with_progress(resp, "acme.com", quiet=False)

        # Then
        self.assertEqual(data, {})

    @responses.activate
    def test_handle_stripped_header(self):

        # Given
        def callback(request):
            self.assertTrue("gzip" in
                            request.headers.get("Accept-Encoding", ""))

            headers = {"Content-Encoding": ""}
            body = self._gzip_compress(b"{}")
            return (200, headers, body)

        responses.add_callback(responses.GET, "https://acme.com/index.json", callback)

        config = Configuration()

        # When
        session = Session.from_configuration(config)
        resp = session.fetch("https://acme.com/index.json")
        data = _fetch_json_with_progress(resp, "acme.com", quiet=False)

        # Then
        self.assertEqual(data, {})

    @responses.activate
    def test_handle_stripped_header_incomplete_data(self):

        # Given
        def callback(request):
            self.assertTrue("gzip" in
                            request.headers.get("Accept-Encoding", ""))

            headers = {"Content-Encoding": ""}
            incomplete_body = self._gzip_compress(b"{}")[:-1]
            return (200, headers, incomplete_body)

        responses.add_callback(responses.GET, "https://acme.com/index.json", callback)

        config = Configuration()

        # When/Then
        session = Session.from_configuration(config)
        resp = session.fetch("https://acme.com/index.json")
        with self.assertRaises(requests.exceptions.ContentDecodingError):
            _fetch_json_with_progress(resp, "acme.com", quiet=False)
