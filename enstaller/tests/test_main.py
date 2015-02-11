import errno
import json
import logging
import ntpath
import os.path
import posixpath
import re
import shutil
import site
import sys
import tempfile
import textwrap

import mock

from egginst.tests.common import mkdtemp, DUMMY_EGG
from egginst.utils import ensure_dir
from egginst.vendor.six import StringIO
from egginst.vendor.six.moves import unittest


from enstaller.auth import UserInfo
from enstaller.config import Configuration
from enstaller.errors import InvalidPythonPathConfiguration
from enstaller.main import (check_prefixes, ensure_authenticated_config,
                            epd_install_confirm, env_option,
                            get_package_path, imports_option, install_req,
                            main, needs_to_downgrade_enstaller,
                            repository_factory, search, setup_proxy_or_die,
                            update_enstaller, _ensure_config_path,
                            _get_enstaller_comparable_version)
from enstaller.main import HOME_ENSTALLER4RC
from enstaller.eggcollect import meta_info_from_prefix
from enstaller.plat import custom_plat
from enstaller.repository import Repository, InstalledPackageMetadata
from enstaller.session import Session
from enstaller.solver import Requirement
from enstaller.utils import PY_VER
from enstaller.vendor import responses
from enstaller.versions.enpkg import EnpkgVersion

import enstaller.tests.common
from .common import (authenticated_config, create_prefix_with_eggs,
                     dummy_installed_package_factory,
                     dummy_repository_package_factory, exception_code,
                     mock_print, mock_index, mock_raw_input, fake_keyring,
                     mocked_session_factory, FakeOptions,
                     R_JSON_AUTH_FREE_RESP, R_JSON_NOAUTH_RESP,
                     DummyAuthenticator)


class TestEnstallerUpdate(unittest.TestCase):
    @mock.patch("enstaller.__is_released__", True)
    def test_no_update_enstaller(self):
        config = Configuration()
        session = mocked_session_factory(config.repository_cache)

        opts = mock.Mock()
        opts.yes = False

        self.assertFalse(update_enstaller(session, Repository(), opts))

    def _test_update_enstaller(self, low_version, high_version):
        config = Configuration()
        session = mocked_session_factory(config.repository_cache)

        enstaller_eggs = [
            dummy_repository_package_factory("enstaller", low_version, 1),
            dummy_repository_package_factory("enstaller", high_version, 1),
        ]
        repository = enstaller.tests.common.repository_factory(enstaller_eggs)

        with mock_raw_input("yes"):
            with mock.patch("enstaller.main.inplace_update", lambda *args: None):
                opts = mock.Mock()
                opts.yes = False
                return update_enstaller(session, repository, opts)

    @mock.patch("enstaller.__version__", "4.6.3")
    @mock.patch("enstaller.__is_released__", True)
    def test_update_enstaller_higher_available(self):
        # low/high versions are below/above any realistic enstaller version
        low_version, high_version = "1.0.0", "666.0.0"
        self.assertTrue(self._test_update_enstaller(low_version, high_version))

    @mock.patch("enstaller.__version__", "4.6.3")
    @mock.patch("enstaller.__is_released__", True)
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
                                        "lib/python{0}/site-packages".
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
                             "Expected to find {0} in PYTHONPATH".
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
                             "Expected to find {0} in PYTHONPATH".
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

        repository = Repository()
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

    @mock.patch("enstaller.main.write_default_config")
    def test_get_config_filename_nothing_anywhere(self, write_default_config):
        # When
        with mock.patch("enstaller.main._get_config_candidate", return_value=None):
            config_path = _ensure_config_path()

        # Then
        self.assertEqual(config_path, HOME_ENSTALLER4RC)
        self.assertTrue(write_default_config.called_with(config_path,
                                                         HOME_ENSTALLER4RC))

    @mock.patch("enstaller.main.write_default_config")
    def test_get_config_filename_nothing_in_sys_prefix(self, write_default_config):
        # Given
        prefix = self.tempdir

        # When
        with mock.patch("enstaller.config.sys.prefix", prefix):
            config_path = _ensure_config_path()

        # Then
        self.assertEqual(config_path, HOME_ENSTALLER4RC)

    @mock.patch("enstaller.main.write_default_config")
    def test_get_config_filename_file_in_sys_prefix(self, write_default_config):
        # Given
        prefix = self.tempdir
        path = os.path.join(prefix, ".enstaller4rc")

        with open(path, "w") as fp:
            fp.write("")

        # When
        with mock.patch("enstaller.config.sys.prefix", prefix):
            config_path = _ensure_config_path()

        # Then
        self.assertEqual(config_path, path)

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
        with Session(DummyAuthenticator(), self.tempdir) as session:
            repository = repository_factory(session, config.indices)

        # Then
        repository.find_package("numpy", "1.8.0-1")
        repository.find_package("scipy", "0.13.3-1")

        self.assertEqual(repository.find_packages("nose"), [])

    def test_setup_proxy_or_die(self):
        # Given
        proxy_string = "http://acme.com:3128"
        config = Configuration()

        # When
        setup_proxy_or_die(config, proxy_string)

        # Then
        self.assertEqual(config.proxy_dict, {"http": "http://acme.com:3128"})

    @unittest.skipIf(sys.version_info < (2, 7),
                     "Bug in 2.6 stdlib for parsing url without scheme")
    def test_setup_proxy_or_die_without_scheme(self):
        # Given
        proxy_string = "acme.com:3128"
        config = Configuration()

        # When
        setup_proxy_or_die(config, proxy_string)

        # Then
        self.assertEqual(config.proxy_dict, {"http": "http://acme.com:3128"})

        # Given
        proxy_string = ":3128"
        config = Configuration()

        # When/Then
        with self.assertRaises(SystemExit) as exc:
            setup_proxy_or_die(config, proxy_string)
        self.assertEqual(exc.exception.code, 1)


class TestSearch(unittest.TestCase):
    def test_no_installed(self):
        config = Configuration()
        config.update(use_webservice=False)

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
        config.update(use_webservice=False)

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
        config.update(use_webservice=False)
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

    @responses.activate
    def test_not_available(self):
        responses.add(responses.GET,
                      "https://acme.com/accounts/user/info/",
                      body=json.dumps(R_JSON_AUTH_FREE_RESP))
        config = Configuration()
        config.update(store_url="https://acme.com")

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

        with Session.from_configuration(config) as session:
            with mkdtemp() as d:
                with mock_print() as m:
                    enpkg = create_prefix_with_eggs(config, d, remote_entries=entries)
                    search(enpkg._remote_repository,
                           enpkg._installed_repository, config, session)

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
        self.maxDiff = None

        # Given
        entry = dummy_repository_package_factory("nose", "1.3.0", 1)
        entry.product = "pypi"
        remote_entries = [entry]
        r_message = textwrap.dedent("""\
        The following packages/requirements are coming from the PyPi repo:

        nose

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

    @responses.activate
    def test_simple(self):
        # Given
        path = os.path.join(self.prefix, "enstaller.yaml")
        responses.add(responses.POST, "http://acme.com/api/v0/json/auth/tokens/auth",
                      body=json.dumps({"token": "dummy token"}))

        with open(path, "wt") as fp:
            fp.write(textwrap.dedent("""\
                    store_url: "http://acme.com"
                    authentication:
                      kind: "simple"
                      username: "foo@acme.com"
                      password: "bar"
            """))

        # When
        # Then No exception
        main(["-s", "numpy", "-c", path])


class TestEnstallerComparableVersion(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_no_egg_install(self):
        # Given
        prefix = self.prefix
        package_name = "enstaller"
        r_version = EnpkgVersion.from_upstream_and_build(enstaller.__version__,
                                                         1)

        # When
        version = _get_enstaller_comparable_version(prefix, package_name)

        # Then
        self.assertEqual(version, r_version)

    def test_egg_install(self):
        # ensure that we use the build number from installed metadata if
        # version and enstaller.__version__ are the same

        # Given
        prefix = self.prefix
        package_name = "enstaller"
        version_string = "2.7.6"
        build = 4
        r_version = EnpkgVersion.from_upstream_and_build(version_string, build)

        json_dict = {
            "arch": None,
            "build": build,
            "ctime": "Mon Oct 20 15:49:19 2014",
            "hook": False,
            "key": "enstaller-{0}-1.egg".format(version_string),
            "name": "enstaller",
            "osdist": None,
            "packages": [],
            "platform": None,
            "python": "2.7",
            "type": "egg",
            "version": version_string,
        }

        meta_info_path = meta_info_from_prefix(prefix, package_name)
        ensure_dir(meta_info_path)
        with open(meta_info_path, "wt") as fp:
            json.dump(json_dict, fp)

        # When
        with mock.patch("enstaller.__version__", version_string):
            version = _get_enstaller_comparable_version(prefix, package_name)

        # Then
        self.assertEqual(version, r_version)

    def test_egg_install_different_versions(self):
        # ensure that we use the build number from installed metadata if
        # version and enstaller.__version__ are the same

        # Given
        prefix = self.prefix
        package_name = "enstaller"
        version_string = "2.7.6"
        build = 4

        json_dict = {
            "arch": None,
            "build": build,
            "ctime": "Mon Oct 20 15:49:19 2014",
            "hook": False,
            "key": "enstaller-{0}-1.egg".format(version_string),
            "name": "enstaller",
            "osdist": None,
            "packages": [],
            "platform": None,
            "python": "2.7",
            "type": "egg",
            "version": version_string,
        }
        r_version = EnpkgVersion.from_upstream_and_build("4.8.0", 1)

        meta_info_path = meta_info_from_prefix(prefix, package_name)
        ensure_dir(meta_info_path)
        with open(meta_info_path, "wt") as fp:
            json.dump(json_dict, fp)

        # When
        with mock.patch("enstaller.__version__", "4.8.0"):
            version = _get_enstaller_comparable_version(prefix, package_name)

        # Then
        self.assertEqual(version, r_version)


class TestConfigurationSetup(unittest.TestCase):
    @responses.activate
    def test_ensure_authenticated_config(self):
        # Given
        r_message = textwrap.dedent("""\
            Could not authenticate as 'nono'
            Please check your credentials/configuration and try again
            (original error is: 'Authentication error: Invalid user login.').


            You can change your authentication details with 'enpkg --userpass'.
        """)

        store_url = "https://acme.com"
        responses.add(responses.GET, store_url + "/accounts/user/info/",
                      body=json.dumps(R_JSON_NOAUTH_RESP))

        config = Configuration()
        config.update(store_url=store_url, auth=("nono", "le petit robot"))

        session = Session.from_configuration(config)

        # When/Then
        with mock_print() as m:
            with self.assertRaises(SystemExit) as e:
                ensure_authenticated_config(config, "", session)

        self.assertEqual(exception_code(e), -1)
        self.assertMultiLineEqual(m.value, r_message)


@mock.patch("enstaller.main.install_req")
class TestMainYamlConfig(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    @mock_index({})
    def test_home_expand(self, install_req):
        # Given
        path = "~/config.yaml"
        args = ["--config-path=~/config.yaml", "foo"]

        r_path = os.path.expanduser(path)

        # When
        with mock.patch("enstaller.main.Configuration.from_yaml_filename",
                        return_value=Configuration()) \
                as mocked_factory:
            with self.assertRaises(SystemExit) as exc:
                main(args)
            self.assertEqual(exception_code(exc), -1)

        # Then
        mocked_factory.assert_called_with(r_path)

    @mock_index({})
    def test_non_existing_config_path(self, install_req):
        # Given
        args = ["--config-path=config.yaml", "foo"]

        # When/Then
        with self.assertRaises(SystemExit) as exc:
            main(args)
        self.assertEqual(exception_code(exc), -1)

    @mock_index({})
    def test_config_path_missing_auth(self, install_req):
        # Given
        path = os.path.join(self.prefix, "config.yaml")
        with open(path, "wt") as fp:
            fp.write("")

        args = ["--config-path=" + path, "foo"]

        r_msg = "Authentication missing from {0!r}\n".format(path)

        # When
        with mock_print() as m:
            with self.assertRaises(SystemExit) as exc:
                main(args)

        # Then
        self.assertEqual(exception_code(exc), -1)
        self.assertEqual(m.value, r_msg)


@mock.patch("enstaller.main.install_req")
@authenticated_config
class TestMain(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    @mock_index({})
    def test_setup_proxy(self, install_req):
        # Given
        args = ["--proxy=http://acme.com:3128", "foo"]

        # When
        with mock.patch("enstaller.main.setup_proxy_or_die") as m:
            main(args)

        # Then
        m.assert_called()
        self.assertEqual(m.call_args[0][1], "http://acme.com:3128")

    @mock_index({})
    def test_user_valid_config(self, install_req):
        # Given
        args = ["--user", "foo"]

        # When
        with mock.patch("enstaller.main.check_prefixes") as m:
            main(args)

        # Then
        m.assert_called_with([site.USER_BASE, os.path.normpath(sys.prefix)])

    @mock_index({})
    def test_user_invalid_config(self, install_req):
        # Given
        r_msg = "Using the --user option, but your PYTHONPATH is not setup " \
                "accordingly"

        args = ["--user", "foo"]

        # When/Then
        with self.assertWarnsRegex(Warning, r_msg):
            main(args)

    @mock_index({})
    def test_max_retries(self, install_req):
        # Given
        args = ["--max-retries", "42"]

        # When
        with mock.patch("enstaller.main.dispatch_commands_with_enpkg") as m:
            main(args)
        config = m.call_args[0][2]

        # Then
        m.assert_called()
        self.assertEqual(config.max_retries, 42)

    @mock_index({})
    def test_quiet(self, install_req):
        # Given
        args = ["foo"]

        # When
        with mock.patch("sys.stdout", new=StringIO()) as m:
            main(args)

        # Then
        self.assertNotEqual(m.getvalue(), "")

        # Given
        args = ["foo", "--quiet"]

        # When
        with mock.patch("sys.stdout", new=StringIO()) as m:
            main(args)

        # Then
        self.assertEqual(m.getvalue(), "")

    @mock_index({})
    def test_verbose_flag(self, install_req):
        # Given
        args = ["foo"]

        # When
        with mock.patch("enstaller.logging.basicConfig") as m:
            main(args)

        # Then
        m.assert_called()
        self.assertEqual(m.call_args[1]["level"], logging.WARN)

        # Given
        args = ["foo", "-v"]

        # When
        with mock.patch("enstaller.logging.basicConfig") as m:
            main(args)

        # Then
        m.assert_called()
        self.assertEqual(m.call_args[1]["level"], logging.INFO)

        # Given
        args = ["foo", "-vv"]

        # When
        with mock.patch("enstaller.main.http_client.HTTPConnection") \
                as fake_connection:
            with mock.patch("enstaller.logging.basicConfig") as m:
                main(args)

        # Then
        fake_connection.assert_not_called()

        m.assert_called()
        self.assertEqual(m.call_args[1]["level"], logging.DEBUG)

        # Given
        args = ["foo", "-vvv"]

        # When
        with mock.patch("enstaller.main.http_client.HTTPConnection") \
                as fake_connection:
            with mock.patch("enstaller.logging.basicConfig") as m:
                main(args)

        # Then
        fake_connection.assert_called()
        self.assertEqual(fake_connection.debuglevel, 1)

        m.assert_called()
        self.assertEqual(m.call_args[1]["level"], logging.DEBUG)
