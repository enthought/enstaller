import errno
import json
import ntpath
import os.path
import posixpath
import re
import shutil
import sys
import tempfile
import textwrap

if sys.version_info < (2, 7):
    import unittest2 as unittest
    # FIXME: this looks quite fishy. On 2.6, with unittest2, the assertRaises
    # context manager does not contain the actual exception object ?
    def exception_code(ctx):
        return ctx.exception
else:
    import unittest
    def exception_code(ctx):
        return ctx.exception.code

import mock

from egginst.main import EggInst
from egginst.tests.common import mkdtemp, DUMMY_EGG


from enstaller.auth import UserInfo
from enstaller.config import Configuration
from enstaller.enpkg import Enpkg
from enstaller.errors import InvalidPythonPathConfiguration
from enstaller.fetch import URLFetcher
from enstaller.main import (check_prefixes, disp_store_info,
                            epd_install_confirm, env_option,
                            get_config_filename, get_package_path,
                            imports_option, info_option,
                            install_from_requirements, install_req,
                            install_time_string, needs_to_downgrade_enstaller,
                            name_egg, print_installed, repository_factory,
                            search, update_all, updates_check,
                            update_enstaller, whats_new)
from enstaller.main import HOME_ENSTALLER4RC, SYS_PREFIX_ENSTALLER4RC
from enstaller.plat import custom_plat
from enstaller.repository import Repository, InstalledPackageMetadata
from enstaller.resolve import Req
from enstaller.utils import PY_VER
from enstaller.vendor import responses

import enstaller.tests.common
from .common import (dummy_installed_package_factory,
                     dummy_repository_package_factory, mock_print,
                     fake_keyring, is_authenticated,
                     FAKE_MD5, FAKE_SIZE)

class TestEnstallerUpdate(unittest.TestCase):
    def test_no_update_enstaller(self):
        config = Configuration()

        enpkg = Enpkg(mock.Mock(), mock.Mock())
        self.assertFalse(update_enstaller(enpkg, config, False, {}))

    def _test_update_enstaller(self, low_version, high_version):
        config = Configuration()

        enstaller_eggs = [
            dummy_repository_package_factory("enstaller", low_version, 1),
            dummy_repository_package_factory("enstaller", high_version, 1),
        ]
        repository = enstaller.tests.common.repository_factory(enstaller_eggs)

        with mock.patch("__builtin__.raw_input", lambda ignored: "y"):
            with mock.patch("enstaller.main.install_req", lambda *args: None):
                enpkg = Enpkg(repository, mock.Mock())
                opts = mock.Mock()
                opts.no_deps = False
                return update_enstaller(enpkg, config, config.autoupdate, opts)

    @mock.patch("enstaller.__version__", "4.6.3")
    @mock.patch("enstaller.main.IS_RELEASED", True)
    def test_update_enstaller_higher_available(self):
        # low/high versions are below/above any realistic enstaller version
        low_version, high_version = "1.0.0", "666.0.0"
        self.assertTrue(self._test_update_enstaller(low_version, high_version))

    @mock.patch("enstaller.__version__", "4.6.3")
    @mock.patch("enstaller.main.IS_RELEASED", True)
    def test_update_enstaller_higher_unavailable(self):
        # both low/high versions are below current enstaller version
        low_version, high_version = "1.0.0", "2.0.0"
        self.assertFalse(self._test_update_enstaller(low_version, high_version))

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

    def test_epd_install_confirm(self):
        for allowed_yes in ("y", "Y", "yes", "YES", "YeS"):
            with mock.patch("__builtin__.raw_input", lambda ignored: allowed_yes):
                self.assertTrue(epd_install_confirm())

        for non_yes in ("n", "N", "no", "NO", "dummy"):
            with mock.patch("__builtin__.raw_input", lambda ignored: non_yes):
                self.assertFalse(epd_install_confirm())

    @mock.patch("sys.platform", "linux2")
    def test_get_package_path_unix(self):
        prefix = "/foo"
        r_site_packages = posixpath.join(prefix, "lib", "python" + PY_VER, "site-packages")

        self.assertEqual(get_package_path(prefix), r_site_packages)

    @mock.patch("sys.platform", "win32")
    def test_get_package_path_windows(self):
        prefix = "c:\\foo"
        r_site_packages = ntpath.join(prefix, "lib", "site-packages")

        self.assertEqual(get_package_path(prefix), r_site_packages)

    @mock.patch("sys.platform", "linux2")
    def test_check_prefixes_unix(self):
        prefixes = ["/foo", "/bar"]
        site_packages = [posixpath.join(prefix,
                                        "lib/python{0}/site-packages". \
                                        format(PY_VER))
                         for prefix in prefixes]

        with mock.patch("sys.path", site_packages):
            check_prefixes(prefixes)

        with mock.patch("sys.path", site_packages[::-1]):
            with self.assertRaises(InvalidPythonPathConfiguration) as e:
                check_prefixes(prefixes)
            message = e.exception.message
            self.assertEqual(message, "Order of path prefixes doesn't match PYTHONPATH")

        with mock.patch("sys.path", []):
            with self.assertRaises(InvalidPythonPathConfiguration) as e:
                check_prefixes(prefixes)
            message = e.exception.message
            self.assertEqual(message,
                             "Expected to find {0} in PYTHONPATH". \
                             format(site_packages[0]))

    @mock.patch("sys.platform", "win32")
    def test_check_prefixes_win32(self):
        prefixes = ["c:\\foo", "c:\\bar"]
        site_packages = [ntpath.join(prefix, "lib", "site-packages")
                         for prefix in prefixes]

        with mock.patch("sys.path", site_packages):
            check_prefixes(prefixes)

        with mock.patch("sys.path", site_packages[::-1]):
            with self.assertRaises(InvalidPythonPathConfiguration) as e:
                check_prefixes(prefixes)
            message = e.exception.message
            self.assertEqual(message, "Order of path prefixes doesn't match PYTHONPATH")

        with mock.patch("sys.path", []):
            with self.assertRaises(InvalidPythonPathConfiguration) as e:
                check_prefixes(prefixes)
            message = e.exception.message
            self.assertEqual(message,
                             "Expected to find {0} in PYTHONPATH". \
                             format(site_packages[0]))

    def test_imports_option_empty(self):
        # Given
        r_output = textwrap.dedent("""\
            Name                 Version              Location
            ============================================================
            """)
        repository = Repository()

        # When
        with mock_print() as m:
            imports_option(repository)

        # Then
        self.assertMultiLineEqual(m.value, r_output)

    def test_imports_option_sys_only(self):
        # Given
        r_output = textwrap.dedent("""\
            Name                 Version              Location
            ============================================================
            dummy                1.0.1-1              sys
            """)

        repository = Repository(sys.prefix)
        metadata = InstalledPackageMetadata.from_egg(DUMMY_EGG,
                                                     "random string",
                                                     sys.prefix)
        repository.add_package(metadata)

        # When
        with mock_print() as m:
            imports_option(repository)

        # Then
        self.assertMultiLineEqual(m.value, r_output)

    def test_env_options(self):
        # Given
        prefix = sys.prefix
        r_output = textwrap.dedent("""\
            Prefixes:
                {0} (sys)
        """.format(prefix))

        # When
        with mock_print() as m:
            env_option([sys.prefix])

        # Then
        self.assertMultiLineEqual(m.value, r_output)

    def test_env_options_multiple_prefixes(self):
        # Given
        if sys.platform == "win32":
            prefixes = ["C:/opt", sys.prefix]
        else:
            prefixes = ["/opt", sys.prefix]
        r_output = textwrap.dedent("""\
            Prefixes:
                {0}
                {1} (sys)
        """.format(prefixes[0], prefixes[1]))

        # When
        with mock_print() as m:
            env_option(prefixes)

        # Then
        self.assertMultiLineEqual(m.value, r_output)

    def test_needs_to_downgrade(self):
        # Given
        reqs = []

        # When/Then
        self.assertFalse(needs_to_downgrade_enstaller(reqs))

        # Given
        reqs = [Req.from_anything("numpy"), Req.from_anything("scipy")]

        # When/Then
        self.assertFalse(needs_to_downgrade_enstaller(reqs))

        # Given
        reqs = [Req.from_anything("enstaller"), Req.from_anything("scipy")]

        # When/Then
        self.assertFalse(needs_to_downgrade_enstaller(reqs))

        # Given
        reqs = [Req.from_anything("enstaller 4.5.1")]

        # When/Then
        self.assertTrue(needs_to_downgrade_enstaller(reqs))

    def test_get_config_filename_sys_config(self):
        # Given
        use_sys_config = True

        # When/Then
        self.assertEqual(get_config_filename(use_sys_config), SYS_PREFIX_ENSTALLER4RC)

    def test_get_config_filename_no_sys_config_default(self):
        # Given
        use_sys_config = False

        # When/Then
        self.assertEqual(get_config_filename(use_sys_config), HOME_ENSTALLER4RC)

    def test_get_config_filename_no_sys_config_with_single_prefix(self):
        # Given
        use_sys_config = False

        # When/Then
        with mock.patch("enstaller.main.configuration_read_search_order",
                        return_value=[self.tempdir]):
            self.assertEqual(get_config_filename(use_sys_config), HOME_ENSTALLER4RC)

        # When/Then
        with mock.patch("enstaller.main.configuration_read_search_order",
                        return_value=[self.tempdir]):
            path = os.path.join(self.tempdir, ".enstaller4rc")
            with open(path, "w") as fp:
                fp.write("")
            self.assertEqual(get_config_filename(use_sys_config), path)

    def _mock_index(self, entries):
        index = dict((entry.key, entry.s3index_data) for entry in entries)

        responses.add(responses.GET,
                      "https://api.enthought.com/eggs/{0}/index.json".format(custom_plat),
                      body=json.dumps(index), status=200,
                      content_type='application/json')

    @responses.activate
    def test_repository_factory(self):
        # Given
        config = Configuration()
        entries = [
            dummy_repository_package_factory("numpy", "1.8.0", 1),
            dummy_repository_package_factory("scipy", "0.13.3", 1),
        ]
        self._mock_index(entries)
        fetcher = URLFetcher(config.repository_cache, config.auth)

        # When
        repository = repository_factory(fetcher, config)

        # Then
        repository.find_package("numpy", "1.8.0-1")
        repository.find_package("scipy", "0.13.3-1")

        self.assertEqual(repository.find_packages("nose"), [])


def _create_repositories(remote_entries=None, installed_entries=None):
    if remote_entries is None:
        remote_entries = []
    if installed_entries is None:
        installed_entries = []

    remote_repository = Repository()
    for remote_entry in remote_entries:
        remote_repository.add_package(remote_entry)
    installed_repository = Repository()
    for installed_entry in installed_entries:
        installed_repository.add_package(installed_entry)

    return remote_repository, installed_repository

def _create_prefix_with_eggs(config, prefix, installed_entries=None, remote_entries=None):
    if remote_entries is None:
        remote_entries = []
    if installed_entries is None:
        installed_entries = []

    repository = enstaller.tests.common.repository_factory(remote_entries)

    enpkg = Enpkg(repository, mock.Mock(), prefixes=[prefix])
    for package in installed_entries:
        package.store_location = prefix
        enpkg._top_installed_repository.add_package(package)
        enpkg._installed_repository.add_package(package)
    return enpkg

class TestInfoStrings(unittest.TestCase):
    def test_print_install_time(self):
        with mkdtemp() as d:
            installed_entries = [dummy_installed_package_factory("dummy",
                                                                 "1.0.1", 1)]
            enpkg = _create_prefix_with_eggs(Configuration(), d, installed_entries)

            self.assertRegexpMatches(install_time_string(enpkg._installed_repository,
                                                         "dummy"),
                                     "dummy-1.0.1-1.egg was installed on:")

            self.assertEqual(install_time_string(enpkg._installed_repository, "ddummy"), "")

    def test_info_option(self):
        self.maxDiff = None

        # Given
        r_output = textwrap.dedent("""\
        Package: enstaller

        Version: 4.6.2-1
            Product: commercial
            Available: True
            Python version: {2}
            Store location: {3}
            MD5: {0}
            Size: {1}
            Requirements: None
        Version: 4.6.3-1
            Product: commercial
            Available: True
            Python version: {2}
            Store location: {3}
            MD5: {0}
            Size: {1}
            Requirements: None
        """.format(FAKE_MD5, FAKE_SIZE, PY_VER, ""))

        entries = [dummy_repository_package_factory("enstaller", "4.6.2", 1),
                   dummy_repository_package_factory("enstaller", "4.6.3", 1)]

        remote_repository, installed_repository = \
                _create_repositories(remote_entries=entries)

        # When
        with mock_print() as m:
            info_option(remote_repository, installed_repository,
                        "enstaller")
        # Then
        self.assertMultiLineEqual(m.value, r_output)

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
            self.assertEqual(m.value, r_out)

            r_out = textwrap.dedent("""\
                Name                 Version              Store
                ============================================================
                """)

            repository = Repository._from_prefixes([d])
            with mock_print() as m:
                print_installed(repository, pat=re.compile("no_dummy"))
            self.assertEqual(m.value, r_out)

class TestSearch(unittest.TestCase):
    def test_no_installed(self):
        config = Configuration()
        config.disable_webservice()

        with mkdtemp() as d:
            # XXX: isn't there a better way to ensure ws at the end of a line
            # are not eaten away ?
            r_output = textwrap.dedent("""\
                Name                   Versions           Product              Note
                ================================================================================
                another_dummy          2.0.0-1            commercial           {0}
                dummy                  0.9.8-1            commercial           {0}
                                       1.0.0-1            commercial           {0}
                """.format(""))
            entries = [dummy_repository_package_factory("dummy", "1.0.0", 1),
                       dummy_repository_package_factory("dummy", "0.9.8", 1),
                       dummy_repository_package_factory("another_dummy", "2.0.0", 1)]
            enpkg = _create_prefix_with_eggs(config, d, remote_entries=entries)

            with mock_print() as m:
                search(enpkg, enpkg._remote_repository,
                       enpkg._top_installed_repository, config, UserInfo(True))
                self.assertMultiLineEqual(m.value, r_output)

    def test_installed(self):
        config = Configuration()
        config.disable_webservice()

        with mkdtemp() as d:
            r_output = textwrap.dedent("""\
                Name                   Versions           Product              Note
                ================================================================================
                dummy                  0.9.8-1            commercial           {0}
                                     * 1.0.1-1            commercial           {0}
                """.format(""))
            entries = [dummy_repository_package_factory("dummy", "1.0.1", 1),
                       dummy_repository_package_factory("dummy", "0.9.8", 1)]
            installed_entries = [dummy_installed_package_factory("dummy", "1.0.1", 1)]
            enpkg = _create_prefix_with_eggs(config, d, installed_entries, entries)

            with mock_print() as m:
                search(enpkg, enpkg._remote_repository,
                       enpkg._installed_repository, config, UserInfo(True))
                self.assertMultiLineEqual(m.value, r_output)

    def test_pattern(self):
        config = Configuration()
        config.disable_webservice()
        with mkdtemp() as d:
            r_output = textwrap.dedent("""\
                Name                   Versions           Product              Note
                ================================================================================
                dummy                  0.9.8-1            commercial           {0}
                                     * 1.0.1-1            commercial           {0}
                """.format(""))
            entries = [dummy_repository_package_factory("dummy", "1.0.1", 1),
                       dummy_repository_package_factory("dummy", "0.9.8", 1),
                       dummy_repository_package_factory("another_package", "2.0.0", 1)]
            installed_entries = [dummy_installed_package_factory("dummy", "1.0.1", 1)]
            enpkg = _create_prefix_with_eggs(config, d, installed_entries, entries)

            with mock_print() as m:
                search(enpkg, enpkg._remote_repository,
                       enpkg._top_installed_repository,
                       config, UserInfo(True),
                       pat=re.compile("dummy"))
                self.assertMultiLineEqual(m.value, r_output)

            r_output = textwrap.dedent("""\
                Name                   Versions           Product              Note
                ================================================================================
                another_package        2.0.0-1            commercial           {0}
                dummy                  0.9.8-1            commercial           {0}
                                     * 1.0.1-1            commercial           {0}
                """.format(""))
            with mock_print() as m:
                search(enpkg, enpkg._remote_repository,
                       enpkg._top_installed_repository, config,
                       UserInfo(True), pat=re.compile(".*"))
                self.assertMultiLineEqual(m.value, r_output)

    def test_not_available(self):
        config = Configuration()

        r_output = textwrap.dedent("""\
            Name                   Versions           Product              Note
            ================================================================================
            another_package        2.0.0-1            commercial           not subscribed to
            dummy                  0.9.8-1            commercial           {0}
                                   1.0.1-1            commercial           {0}
            Note: some of those packages are not available at your current
            subscription level ('Canopy / EPD Free').
            """.format(""))
        another_entry = dummy_repository_package_factory("another_package", "2.0.0", 1)
        another_entry.available = False

        entries = [dummy_repository_package_factory("dummy", "1.0.1", 1),
                   dummy_repository_package_factory("dummy", "0.9.8", 1),
                   another_entry]

        with mkdtemp() as d:
            with mock_print() as m:
                enpkg = _create_prefix_with_eggs(config, d, remote_entries=entries)
                search(enpkg, enpkg._remote_repository,
                       enpkg._installed_repository, config, UserInfo(True))

                self.assertMultiLineEqual(m.value, r_output)

class TestUpdatesCheck(unittest.TestCase):
    def test_update_check_new_available(self):
        entries = [dummy_repository_package_factory("dummy", "1.2.0", 1),
                   dummy_repository_package_factory("dummy", "0.9.8", 1)]
        installed_entries = [
                dummy_installed_package_factory("dummy", "1.0.1", 1)
        ]

        with mkdtemp() as d:
            enpkg = _create_prefix_with_eggs(Configuration(), d,
                                             installed_entries, entries)

            updates, EPD_update =  updates_check(enpkg._remote_repository,
                                                 enpkg._installed_repository)

            self.assertEqual(EPD_update, [])
            self.assertEqual(len(updates), 1)
            update0 = updates[0]
            self.assertItemsEqual(update0.keys(), ["current", "update"])
            self.assertEqual(update0["current"]["version"], "1.0.1")
            self.assertEqual(update0["update"].version, "1.2.0")

    def test_update_check_no_new_available(self):
        entries = [dummy_repository_package_factory("dummy", "1.0.0", 1),
                   dummy_repository_package_factory("dummy", "0.9.8", 1)]
        installed_entries = [
                dummy_installed_package_factory("dummy", "1.0.1", 1)
        ]

        with mkdtemp() as d:
            enpkg = _create_prefix_with_eggs(Configuration(), d, installed_entries, entries)

            updates, EPD_update =  updates_check(enpkg._remote_repository,
                                                 enpkg._installed_repository)

            self.assertEqual(EPD_update, [])
            self.assertEqual(updates, [])

    def test_update_check_no_available(self):
        # Given
        installed_entries = [
                dummy_installed_package_factory("dummy", "1.0.1", 1)
        ]

        remote, installed = \
                _create_repositories(installed_entries=installed_entries)

        # When
        updates, EPD_update =  updates_check(remote, installed)

        # Then
        self.assertEqual(EPD_update, [])
        self.assertEqual(updates, [])

    def test_update_check_epd(self):
        # Given
        installed_entries = [dummy_installed_package_factory("EPD", "7.2", 1)]
        remote_entries = [dummy_repository_package_factory("EPD", "7.3", 1)]

        remote, installed = _create_repositories(remote_entries,
                                                 installed_entries)

        # When
        updates, EPD_update =  updates_check(remote, installed)

        # Then
        self.assertEqual(updates, [])
        self.assertEqual(len(EPD_update), 1)

        epd_update0 = EPD_update[0]
        self.assertItemsEqual(epd_update0.keys(), ["current", "update"])
        self.assertEqual(epd_update0["current"]["version"], "7.2")
        self.assertEqual(epd_update0["update"].version, "7.3")

    def test_whats_new_no_new_epd(self):
        # Given
        r_output = textwrap.dedent("""\
            Name                 installed            available
            ============================================================
            scipy                0.12.0-1             0.13.0-1
            numpy                1.7.1-1              1.7.1-2
            """)
        installed_entries = [
            dummy_installed_package_factory("numpy", "1.7.1", 1),
            dummy_installed_package_factory("scipy", "0.12.0", 1)
        ]
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.7.1", 2),
            dummy_repository_package_factory("scipy", "0.13.0", 1)
        ]

        remote, installed = _create_repositories(remote_entries,
                                                 installed_entries)

        # When
        with mock_print() as m:
            whats_new(remote, installed)

        # Then

        # FIXME: we splitlines and compared wo caring about order, as
        # the actual line order depends on dict ordering from
        # EggCollection.query_installed.
        self.assertItemsEqual(m.value.splitlines(), r_output.splitlines())

    def test_whats_new_new_epd(self):
        # Given
        r_output = "EPD 7.3-2 is available. To update to it (with " \
                   "confirmation warning), run 'enpkg epd'.\n"
        installed_entries = [
            dummy_installed_package_factory("EPD", "7.2", 1),
        ]
        remote_entries = [
            dummy_repository_package_factory("EPD", "7.3", 2),
        ]

        remote, installed = _create_repositories(remote_entries,
                                                 installed_entries)

        # When
        with mock_print() as m:
            whats_new(remote, installed)

        # Then
        self.assertMultiLineEqual(m.value, r_output)

    def test_whats_new_no_updates(self):
        # Given
        r_output = "No new version of any installed package is available\n"

        installed_entries = [
            dummy_installed_package_factory("numpy", "1.7.1", 2),
            dummy_installed_package_factory("scipy", "0.13.0", 1)
        ]
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.7.1", 1),
            dummy_repository_package_factory("scipy", "0.12.0", 1)
        ]

        remote, installed = _create_repositories(remote_entries,
                                                 installed_entries)

        # When
        with mock_print() as m:
            whats_new(remote, installed)

        # Then
        self.assertMultiLineEqual(m.value, r_output)

    def test_update_all_no_updates(self):
        r_output = "No new version of any installed package is available\n"
        config = Configuration()

        installed_entries = [
            dummy_installed_package_factory("numpy", "1.7.1", 2),
            dummy_installed_package_factory("scipy", "0.13.0", 1)
        ]
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.7.1", 1),
            dummy_repository_package_factory("scipy", "0.12.0", 1)
        ]

        with mkdtemp() as d:
            enpkg = _create_prefix_with_eggs(config, d,
                    installed_entries, remote_entries)
            with mock_print() as m:
                update_all(enpkg, config, FakeOptions())
                self.assertMultiLineEqual(m.value, r_output)

    def test_update_all_no_epd_updates(self):
        r_output = textwrap.dedent("""\
        The following updates and their dependencies will be installed
        Name                 installed            available
        ============================================================
        scipy                0.13.0-1             0.13.2-1
        """)
        config = Configuration()

        installed_entries = [
            dummy_installed_package_factory("numpy", "1.7.1", 2),
            dummy_installed_package_factory("scipy", "0.13.0", 1),
            dummy_installed_package_factory("epd", "7.3", 1),
        ]
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.7.1", 1),
            dummy_repository_package_factory("scipy", "0.13.2", 1),
            dummy_repository_package_factory("epd", "7.3", 1),
        ]

        with mkdtemp() as d:
            enpkg = _create_prefix_with_eggs(config, d, installed_entries, remote_entries)
            with mock.patch("enstaller.main.install_req") as mocked_install_req:
                with mock_print() as m:
                    update_all(enpkg, config, FakeOptions())
                    self.assertMultiLineEqual(m.value, r_output)
                    mocked_install_req.assert_called()

    def test_update_all_epd_updates(self):
        r_output = textwrap.dedent("""\
        EPD 7.3-2 is available. To update to it (with confirmation warning), run 'enpkg epd'.
        The following updates and their dependencies will be installed
        Name                 installed            available
        ============================================================
        scipy                0.13.0-1             0.13.2-1
        """)
        config = Configuration()

        installed_entries = [
            dummy_installed_package_factory("numpy", "1.7.1", 2),
            dummy_installed_package_factory("scipy", "0.13.0", 1),
            dummy_installed_package_factory("epd", "7.3", 1),
        ]
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.7.1", 1),
            dummy_repository_package_factory("scipy", "0.13.2", 1),
            dummy_repository_package_factory("epd", "7.3", 2),
        ]

        with mkdtemp() as d:
            enpkg = _create_prefix_with_eggs(config, d, installed_entries, remote_entries)
            with mock.patch("enstaller.main.install_req") as mocked_install_req:
                with mock_print() as m:
                    update_all(enpkg, config, FakeOptions())
                    self.assertMultiLineEqual(m.value, r_output)
                    mocked_install_req.assert_called()

class FakeOptions(object):
    def __init__(self):
        self.force = False
        self.forceall = False
        self.no_deps = False
        self.yes = False


class TestInstallFromRequirements(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_install_from_requirements(self):
        # Given
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.8.0", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
            dummy_repository_package_factory("nose", "1.2.1", 2),
            dummy_repository_package_factory("nose", "1.3.0", 1)
        ]

        requirements_file = os.path.join(self.prefix, "requirements.txt")
        with open(requirements_file, "w") as fp:
            fp.write("numpy 1.8.0-1\nnose 1.2.1-1")

        config = Configuration()
        enpkg = _create_prefix_with_eggs(config, self.prefix, [], remote_entries)
        args = FakeOptions()
        args.requirements = requirements_file

        # When
        with mock.patch("enstaller.main.install_req") as mocked_install_req:
            install_from_requirements(enpkg, config, args)

        # Then
        mocked_install_req.assert_has_calls(
            [mock.call(enpkg, config, "numpy 1.8.0-1", args),
             mock.call(enpkg, config, "nose 1.2.1-1", args)])


@fake_keyring
class TestInstallReq(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_simple_install(self):
        remote_entries = [
            dummy_repository_package_factory("nose", "1.3.0", 1)
        ]

        with mock.patch("enstaller.main.Enpkg.execute") as m:
            enpkg = _create_prefix_with_eggs(Configuration(), self.prefix, [],
                    remote_entries)
            install_req(enpkg, Configuration(), "nose", FakeOptions())
            m.assert_called_with([('fetch_0', 'nose-1.3.0-1.egg'),
                                  ('install', 'nose-1.3.0-1.egg')])

    def test_simple_non_existing_requirement(self):
        config = Configuration()
        r_error_string = "No egg found for requirement 'nono_le_petit_robot'.\n"
        non_existing_requirement = "nono_le_petit_robot"

        with mock.patch("enstaller.main.Enpkg.execute") as mocked_execute:
            enpkg = _create_prefix_with_eggs(config, self.prefix, [])
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
            enpkg = _create_prefix_with_eggs(config, self.prefix,
                                             installed_entries, remote_entries)
            install_req(enpkg, config, "nose", FakeOptions())
            m.assert_called_with([])

    @is_authenticated
    def test_install_not_available(self):
        config = Configuration()

        nose = dummy_repository_package_factory("nose", "1.3.0", 1)
        nose.available = False
        remote_entries = [nose]

        enpkg = _create_prefix_with_eggs(config, self.prefix, [], remote_entries)

        with mock.patch("enstaller.main.Enpkg.execute"):
            with mock.patch("enstaller.config.subscription_message") as subscription_message:
                with self.assertRaises(SystemExit) as e:
                    install_req(enpkg, config, "nose", FakeOptions())
                subscription_message.assert_called()
                self.assertEqual(exception_code(e), 1)

    @is_authenticated
    def test_recursive_install_unavailable_dependency(self):
        config = Configuration()
        config.set_auth("nono", "le gros robot")

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
            enpkg = _create_prefix_with_eggs(config, self.prefix, [], remote_entries)
            with mock_print() as m:
                with self.assertRaises(SystemExit):
                    install_req(enpkg, config, "scipy", FakeOptions())
                self.assertMultiLineEqual(m.value, r_output)

    @mock.patch("sys.platform", "darwin")
    def test_os_error_darwin(self):
        config = Configuration()

        remote_entries = [
            dummy_repository_package_factory("nose", "1.3.0", 1)
        ]

        with mock.patch("enstaller.main.Enpkg.execute") as m:
            error = OSError()
            error.errno = errno.EACCES
            m.side_effect = error
            enpkg = _create_prefix_with_eggs(config, self.prefix, [], remote_entries)
            with self.assertRaises(SystemExit):
                install_req(enpkg, config, "nose", FakeOptions())

    @mock.patch("sys.platform", "linux2")
    def test_os_error(self):
        config = Configuration()

        remote_entries = [
            dummy_repository_package_factory("nose", "1.3.0", 1)
        ]

        with mock.patch("enstaller.main.Enpkg.execute") as m:
            error = OSError()
            error.errno = errno.EACCES
            m.side_effect = error
            enpkg = _create_prefix_with_eggs(config, self.prefix, [], remote_entries)
            with self.assertRaises(OSError):
                install_req(enpkg, config, "nose", FakeOptions())

    def test_simple_install_pypi(self):
        # Given
        entry = dummy_repository_package_factory("nose", "1.3.0", 1)
        entry.product = "pypi"
        remote_entries = [entry]
        r_message = textwrap.dedent("""\
        The following packages are coming from the PyPi repo:

        'nose-1.3.0-1'

        The PyPi repository which contains >10,000 untested ("as is")
        packages. Some packages are licensed under GPL or other licenses
        which are prohibited for some users. Dependencies may not be
        provided. If you need an updated version or if the installation
        fails due to unmet dependencies, the Knowledge Base article
        Installing external packages into Canopy Python
        (https://support.enthought.com/entries/23389761) may help you with
        installing it.

        """)

        # When
        with mock.patch("__builtin__.raw_input", return_value="y"):
            with mock_print() as mocked_print:
                with mock.patch("enstaller.main.Enpkg.execute") as m:
                    enpkg = _create_prefix_with_eggs(Configuration(), self.prefix, [],
                                                     remote_entries)
                    install_req(enpkg, Configuration(), "nose", FakeOptions())

        # Then
        self.assertMultiLineEqual(mocked_print.value, r_message)
        m.assert_called_with([('fetch_0', 'nose-1.3.0-1.egg'),
                              ('install', 'nose-1.3.0-1.egg')])
