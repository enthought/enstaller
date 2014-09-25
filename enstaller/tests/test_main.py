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
from enstaller.main import (check_prefixes,
                            epd_install_confirm, env_option,
                            get_config_filename, get_package_path,
                            imports_option,
                            install_from_requirements, install_req,
                            main,
                            needs_to_downgrade_enstaller,
                            repository_factory,
                            search, update_all,
                            update_enstaller, whats_new)
from enstaller.main import HOME_ENSTALLER4RC, SYS_PREFIX_ENSTALLER4RC
from enstaller.plat import custom_plat
from enstaller.repository import Repository, InstalledPackageMetadata
from enstaller.session import Session
from enstaller.solver import Requirement
from enstaller.utils import PY_VER
from enstaller.vendor import responses

import enstaller.tests.common
from .common import (create_prefix_with_eggs,
                     dummy_installed_package_factory,
                     dummy_repository_package_factory, mock_print,
                     mock_raw_input, fake_keyring,
                     mock_fetcher_factory, unconnected_enpkg_factory,
                     FakeOptions, FAKE_MD5, FAKE_SIZE, DummyAuthenticator)

class TestEnstallerUpdate(unittest.TestCase):
    def test_no_update_enstaller(self):
        config = Configuration()

        enpkg = unconnected_enpkg_factory()
        self.assertFalse(update_enstaller(enpkg, config, False, {}))

    def _test_update_enstaller(self, low_version, high_version):
        config = Configuration()

        enstaller_eggs = [
            dummy_repository_package_factory("enstaller", low_version, 1),
            dummy_repository_package_factory("enstaller", high_version, 1),
        ]
        repository = enstaller.tests.common.repository_factory(enstaller_eggs)

        with mock_raw_input("yes"):
            with mock.patch("enstaller.main.install_req", lambda *args: None):
                enpkg = Enpkg(repository,
                              mock_fetcher_factory(config.repository_cache))
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

    def test_epd_install_confirm(self):
        for allowed_yes in ("y", "Y", "yes", "YES", "YeS"):
            with mock_raw_input(allowed_yes):
                self.assertTrue(epd_install_confirm())

        for non_yes in ("n", "N", "no", "NO", "dummy"):
            with mock_raw_input(non_yes):
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
            message = str(e.exception)
            self.assertEqual(message,
                             "Order of path prefixes doesn't match PYTHONPATH")

        with mock.patch("sys.path", []):
            with self.assertRaises(InvalidPythonPathConfiguration) as e:
                check_prefixes(prefixes)
            message = str(e.exception)
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
            message = str(e.exception)
            self.assertEqual(message, "Order of path prefixes doesn't match PYTHONPATH")

        with mock.patch("sys.path", []):
            with self.assertRaises(InvalidPythonPathConfiguration) as e:
                check_prefixes(prefixes)
            message = str(e.exception)
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
        reqs = [Requirement.from_anything("numpy"),
                Requirement.from_anything("scipy")]

        # When/Then
        self.assertFalse(needs_to_downgrade_enstaller(reqs))

        # Given
        reqs = [Requirement.from_anything("enstaller"),
                Requirement.from_anything("scipy")]

        # When/Then
        self.assertFalse(needs_to_downgrade_enstaller(reqs))

        # Given
        reqs = [Requirement.from_anything("enstaller 4.5.1")]

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

        # When
        repository = repository_factory(Session(DummyAuthenticator(),
                                                self.tempdir),
                                        config.indices)

        # Then
        repository.find_package("numpy", "1.8.0-1")
        repository.find_package("scipy", "0.13.3-1")

        self.assertEqual(repository.find_packages("nose"), [])


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
            enpkg = create_prefix_with_eggs(config, d, remote_entries=entries)

            with mock_print() as m:
                search(enpkg._remote_repository,
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
            enpkg = create_prefix_with_eggs(config, d, installed_entries, entries)

            with mock_print() as m:
                search(enpkg._remote_repository,
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
            enpkg = create_prefix_with_eggs(config, d, installed_entries, entries)

            with mock_print() as m:
                search(enpkg._remote_repository,
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
                search(enpkg._remote_repository,
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
                enpkg = create_prefix_with_eggs(config, d, remote_entries=entries)
                search(enpkg._remote_repository,
                       enpkg._installed_repository, config, UserInfo(True))

                self.assertMultiLineEqual(m.value, r_output)

@fake_keyring
class TestInstallRequirement(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

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
            enpkg = create_prefix_with_eggs(config, self.prefix, [], remote_entries)
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
            enpkg = create_prefix_with_eggs(config, self.prefix, [], remote_entries)
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

        Are you sure that you wish to proceed?  (y/[n]) 
        """)

        # When
        with mock_print() as mocked_print:
            with mock_raw_input("yes"):
                with mock.patch("enstaller.main.Enpkg.execute") as m:
                    enpkg = create_prefix_with_eggs(Configuration(),
                                                     self.prefix, [],
                                                     remote_entries)
                    install_req(enpkg, Configuration(), "nose", FakeOptions())

        # Then
        self.assertMultiLineEqual(mocked_print.value, r_message)
        m.assert_called_with([('fetch', 'nose-1.3.0-1.egg'),
                              ('install', 'nose-1.3.0-1.egg')])


class TestCustomConfigPath(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_simple(self):
        # Given
        path = os.path.join(self.prefix, "enstaller.yaml")

        with open(path, "wt") as fp:
            fp.write(textwrap.dedent("""\
                    store_url: "http://acme.com"
                    authentication:
                      username: "foo@acme.com"
                      password: "bar"
            """))

        # When
        # Then No exception
        main(["-s", "numpy", "-c", path])
