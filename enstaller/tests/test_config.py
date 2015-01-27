import os.path
import platform
import shutil
import sys
import tempfile
import textwrap

import mock

from egginst.tests.common import mkdtemp
from egginst.vendor.six import StringIO
from egginst.vendor.six.moves import unittest

from enstaller.plat import custom_plat

from enstaller import __version__

from enstaller.auth import APITokenAuth, UserPasswordAuth
from enstaller.config import (prepend_url, print_config,
                              _is_using_epd_username, convert_auth_if_required,
                              _keyring_backend_name, write_default_config)
from enstaller.config import (KEYRING_SERVICE_NAME,
                              Configuration, add_url)
from enstaller.session import Session
from enstaller.errors import (EnstallerException,
                              InvalidConfiguration)
from enstaller.utils import PY_VER

from .common import (make_keyring_available_context, make_keyring_unavailable,
                     mock_print, fake_keyring_context,
                     fake_keyring, DummyAuthenticator)

FAKE_USER = "john.doe"
FAKE_PASSWORD = "fake_password"
FAKE_AUTH = UserPasswordAuth(FAKE_USER, FAKE_PASSWORD)
FAKE_CREDS = UserPasswordAuth(FAKE_USER, FAKE_PASSWORD)._encoded_auth


class TestWriteConfig(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, ".enstaller4rc")

    def tearDown(self):
        shutil.rmtree(self.d)

    @make_keyring_unavailable
    def test_simple(self):
        config = Configuration()
        config.update(auth=(FAKE_USER, FAKE_PASSWORD))
        config.write(self.f)

        config = Configuration.from_file(self.f)

        self.assertEqual(config.auth._encoded_auth, FAKE_CREDS)
        self.assertEqual(config.autoupdate, True)
        self.assertEqual(config.proxy, None)
        self.assertEqual(config.proxy_dict, {})
        self.assertEqual(config.use_webservice, True)
        self.assertEqual(config.webservice_entry_point,
                         "https://api.enthought.com/eggs/{0}/".format(custom_plat))
        self.assertEqual(config.api_url,
                         "https://api.enthought.com/accounts/user/info/")

    @make_keyring_unavailable
    def test_simple_with_proxy(self):
        proxystr = "http://acme.com:3128"

        config = Configuration()
        config.update(proxy=proxystr)
        config.write(self.f)

        config = Configuration.from_file(self.f)
        self.assertEqual(str(config.proxy), proxystr)
        self.assertEqual(config.proxy_dict, {"http": proxystr})

    def test_add_url(self):
        # Given
        path = os.path.join(self.d, "foo.cfg")

        config = Configuration()
        config.write(path)

        url = "http://acme.com/{PLATFORM}/"

        # When
        add_url(path, config, url)

        # Then
        with open(path, "r") as fp:
            data = fp.read()
            self.assertRegex(data, "http://acme.com")

    @make_keyring_unavailable
    def test_change_store_url(self):
        config = Configuration()
        config.update(auth=(FAKE_USER, FAKE_PASSWORD))
        config.write(self.f)

        config = Configuration.from_file(self.f)
        config.update(store_url="https://acme.com")

        self.assertEqual(config.auth._encoded_auth, FAKE_CREDS)
        self.assertEqual(config.autoupdate, True)
        self.assertEqual(config.proxy, None)
        self.assertEqual(config.use_webservice, True)
        self.assertEqual(config.webservice_entry_point,
                         "https://acme.com/eggs/{0}/".format(custom_plat))
        self.assertEqual(config.api_url,
                         "https://acme.com/accounts/user/info/")


class TestConfigKeyringConversion(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_use_epd_username(self):
        data = "EPD_auth = '{0}'".format(FAKE_CREDS)

        self.assertFalse(_is_using_epd_username(StringIO(data)))

        data = "#EPD_auth = '{0}'".format(FAKE_CREDS)
        self.assertFalse(_is_using_epd_username(StringIO(data)))

        data = textwrap.dedent("""\
            #EPD_auth = '{0}'
            EPD_username = '{1}'
        """).format(FAKE_CREDS, FAKE_USER)
        self.assertTrue(_is_using_epd_username(StringIO(data)))

    @fake_keyring
    def test_conversion(self):
        """
        Ensure we don't convert EPD_auth to using keyring.
        """
        path = os.path.join(self.prefix, "some_config_file")
        old_config = "EPD_auth = '{0}'".format(FAKE_CREDS)

        with open(path, "w") as fp:
            fp.write(old_config)

        self.assertFalse(convert_auth_if_required(path))

    @fake_keyring
    def test_username_to_auth_conversion(self):
        """
        Ensure we don't convert EPD_auth to using keyring.
        """
        # Given
        r_content = "EPD_auth = '{0}'".format(FAKE_CREDS)
        path = os.path.join(self.prefix, ".enstaller4rc")

        old_config = "EPD_username = '{0}'".format(FAKE_USER)
        with open(path, "w") as fp:
            fp.write(old_config)

        with fake_keyring_context() as mocked_keyring:
            mocked_keyring.set_password(KEYRING_SERVICE_NAME, FAKE_USER,
                                        FAKE_PASSWORD)

            # When
            converted = convert_auth_if_required(path)

            # Then
            self.assertTrue(converted)
            with open(path) as fp:
                self.assertMultiLineEqual(fp.read(), r_content)

    @fake_keyring
    def test_auth_conversion_without_password_in_keyring(self):
        # Given
        path = os.path.join(self.prefix, ".enstaller4rc")
        old_config = "EPD_username = '{0}'".format(FAKE_USER)
        with open(path, "w") as fp:
            fp.write(old_config)

        with fake_keyring_context():
            # When/Then
            with self.assertRaises(EnstallerException):
                convert_auth_if_required(path)


class TestGetAuth(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, ".enstaller4rc")

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_with_keyring(self):
        with make_keyring_available_context() as mocked_keyring:
            config = Configuration()
            config.update(auth=(FAKE_USER, FAKE_PASSWORD))

            self.assertEqual(config.auth,
                             UserPasswordAuth(FAKE_USER, FAKE_PASSWORD))
            self.assertFalse(mocked_keyring.set_password.called)

    @make_keyring_unavailable
    def test_with_auth(self):
        config = Configuration()
        config.update(auth=(FAKE_USER, FAKE_PASSWORD))

        self.assertEqual(config.auth, FAKE_AUTH)

    @make_keyring_unavailable
    def test_without_auth_or_keyring(self):
        config = Configuration()
        self.assertIsNone(config.auth)


class TestWriteAndChangeAuth(unittest.TestCase):
    def test_simple_set_auth(self):
        # Given
        config = Configuration()

        # When/Then
        self.assertIsNone(config.auth)

        # Given
        config = Configuration()

        # When/Then
        with self.assertRaises(InvalidConfiguration):
            config.update(auth=("", ""))

        # Given
        config = Configuration()
        config.update(auth=("yoyoma", ""))

        # When/Then
        self.assertIsNotNone(config.auth)

    @make_keyring_unavailable
    def test_change_existing_config_file(self):
        r_new_password = "ouioui_dans_sa_petite_voiture"
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        config = Configuration.from_file(fp.name)
        self.assertEqual(config.auth, FAKE_AUTH)

        config.update(auth=(FAKE_USER, r_new_password))
        config._change_auth(fp.name)
        new_config = Configuration.from_file(fp.name)

        self.assertEqual(new_config.auth,
                         UserPasswordAuth(FAKE_USER, r_new_password))

    @make_keyring_unavailable
    def test_change_existing_config_file_empty_username(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        config = Configuration.from_file(fp.name)
        self.assertEqual(config.auth, FAKE_AUTH)

        config.reset_auth()
        config._change_auth(fp.name)

        new_config = Configuration.from_file(fp.name)
        self.assertIsNone(new_config.auth)

    def test_change_existing_config_file_without_keyring(self):
        # Given
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        # When
        config = Configuration.from_file(fp.name)
        config.update(auth=("user", "dummy"))
        config._change_auth(fp.name)

        # Then
        with open(fp.name, "r") as f:
            content = f.read()
            self.assertNotRegex(content, "EPD_username")
            self.assertRegex(content, "EPD_auth")
        config = Configuration.from_file(fp.name)
        self.assertEqual(config.auth, UserPasswordAuth("user", "dummy"))

    @make_keyring_unavailable
    def test_change_empty_config_file_empty_username(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            fp.write("")

        config = Configuration.from_file(fp.name)
        self.assertIsNone(config.auth)

        config.update(auth=(FAKE_USER, FAKE_PASSWORD))
        self.assertEqual(config.auth,
                         UserPasswordAuth(FAKE_USER, FAKE_PASSWORD))

    @make_keyring_unavailable
    def test_no_config_file(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            fp.write("")

        config = Configuration()
        self.assertIsNone(config.auth)

        config.update(auth=(FAKE_USER, FAKE_PASSWORD))
        config.write(fp.name)

        new_config = Configuration.from_file(fp.name)
        self.assertEqual(new_config.auth, FAKE_AUTH)

    @make_keyring_unavailable
    def test_change_auth_wo_existing_auth(self):
        r_output = "EPD_auth = '{0}'\n".format(FAKE_CREDS)

        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            fp.write("")

        config = Configuration.from_file(fp.name)
        config.update(auth=(FAKE_USER, FAKE_PASSWORD))
        config._change_auth(fp.name)

        with open(fp.name) as fp:
            self.assertMultiLineEqual(fp.read(), r_output)

    # FIXME: do we really want to revert the behaviour of change_auth() with
    # auth == (None, None) to do nothing ?
    @unittest.expectedFailure
    @make_keyring_unavailable
    def test_change_config_file_empty_auth(self):
        config_data = "EPD_auth = '{0}'".format(FAKE_CREDS)
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            fp.write(config_data)

        config = Configuration.from_file(fp.name)
        config.update(auth=(None, None))
        config._change_auth(fp.name)

        with open(fp.name, "r") as fp:
            self.assertEqual(fp.read(), config_data)


class TestAuthenticationConfiguration(unittest.TestCase):
    @make_keyring_unavailable
    def test_without_configuration_no_keyring(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            fp.write("")

        config = Configuration.from_file(fp.name)
        self.assertIsNone(config.auth)

    def test_without_configuration_with_keyring(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            fp.write("")

        with mock.patch("enstaller.config.keyring"):
            config = Configuration.from_file(fp.name)
            self.assertIsNone(config.auth)

    @make_keyring_unavailable
    def test_with_configuration_no_keyring(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            auth_line = "EPD_auth = '{0}'".format(FAKE_CREDS)
            fp.write(auth_line)

        config = Configuration.from_file(fp.name)
        self.assertIsNotNone(config.auth)

    def test_with_configuration_with_keyring(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            auth_line = "EPD_username = '{0}'".format(FAKE_USER)
            fp.write(auth_line)

        mocked_keyring = mock.Mock(["get_password"])
        with mock.patch("enstaller.config.keyring", mocked_keyring):
            config = Configuration.from_file(fp.name)
            self.assertIsNotNone(config.auth)


class TestConfigurationParsing(unittest.TestCase):
    def test_parse_simple_unsupported_entry(self):
        # XXX: ideally, we would like something like with self.assertWarns to
        # check for the warning, but backporting the python 3.3 code to
        # unittest2 is a bit painful.
        with mock.patch("enstaller.config.warnings.warn") as m:
            Configuration.from_file(StringIO("nono = 'le petit robot'"))
            m.assert_called_with('Unsupported configuration setting nono, ignored')

    @make_keyring_unavailable
    def test_epd_auth_wo_keyring(self):
        s = StringIO("EPD_auth = '{0}'".format(FAKE_CREDS))

        config = Configuration.from_file(s)
        self.assertEqual(config.auth, FAKE_AUTH)

    @make_keyring_unavailable
    def test_epd_username_wo_keyring(self):
        """
        Ensure config auth correctly reports itself as non configured when
        using EPD_username but keyring is not available to get password.
        """
        s = StringIO("EPD_username = '{0}'".format(FAKE_USER))

        config = Configuration.from_file(s)
        self.assertIsNone(config.auth)

    def test_epd_username(self):
        with fake_keyring_context() as mocked_keyring:
            mocked_keyring.set_password(KEYRING_SERVICE_NAME, FAKE_USER, FAKE_PASSWORD)

            s = StringIO("EPD_username = '{0}'".format(FAKE_USER))
            config = Configuration.from_file(s)

            self.assertEqual(config.auth, FAKE_AUTH)
            self.assertEqual(config.auth._encoded_auth, FAKE_CREDS)

    def test_epd_auth(self):
        """
        Ensure config auth information is properly set-up when using EPD_auth
        """
        s = StringIO("EPD_auth = '{0}'".format(FAKE_CREDS))
        config = Configuration.from_file(s)

        self.assertEqual(config.auth, FAKE_AUTH)

    def test_store_kind(self):
        """
        Ensure config auth information is properly set-up when using EPD_auth
        """
        # Given
        config = Configuration()

        # When
        config.update(store_url="http://acme.com")

        # Then
        self.assertEqual(config.store_kind, "legacy")
        self.assertEqual(config.store_url, "http://acme.com")

        # Given
        config = Configuration()

        # When
        config.update(store_url="brood+http://acme.com")

        # Then
        self.assertEqual(config.store_kind, "brood")
        self.assertEqual(config.store_url, "http://acme.com")

        # Given
        s = StringIO("store_url = 'http://acme.com'")

        # When
        config = Configuration.from_file(s)

        # Then
        self.assertEqual(config.store_kind, "legacy")
        self.assertEqual(config.store_url, "http://acme.com")

        # Given
        s = StringIO("store_url = 'brood+http://acme.com'")

        # When
        config = Configuration.from_file(s)

        # Then
        self.assertEqual(config.store_kind, "brood")
        self.assertEqual(config.store_url, "http://acme.com")

    def test_api_token(self):
        # Given
        config = Configuration()

        # When
        config.update(auth=APITokenAuth("dummy token"))

        # Then
        self.assertEqual(config.auth, APITokenAuth("dummy token"))

        # Given
        data = StringIO("api_token = 'yoyo'")

        # When
        config = Configuration.from_file(data)

        # Then
        self.assertEqual(config.auth, APITokenAuth("yoyo"))

    def test_both_auth_set(self):
        # Given
        data = "EPD_auth = '{0}'\napi_token = 'token'"
        data = StringIO(data.format(FAKE_CREDS))

        msg = "Both 'EPD_auth' and 'api_token' set in configuration." \
              "\nYou should remove one of those for consistent " \
              "behaviour."

        # When
        with self.assertWarnsRegex(Warning, msg):
            Configuration.from_file(data)


class TestConfigurationPrint(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_simple_in_memory(self):
        output_template = textwrap.dedent("""\
            Python version: {pyver}
            enstaller version: {version}
            sys.prefix: {sys_prefix}
            platform: {platform}
            architecture: {arch}
            use_webservice: True
            keyring backend: {keyring_backend}
            settings:
                prefix = {{prefix}}
                repository_cache = {{repository_cache}}
                noapp = False
                proxy = None
            No valid auth information in configuration, cannot authenticate.
            You are not logged in.  To log in, type 'enpkg --userpass'.
        """).format(pyver=PY_VER, sys_prefix=os.path.normpath(sys.prefix),
                    version=__version__, platform=platform.platform(),
                    arch=platform.architecture()[0],
                    keyring_backend=_keyring_backend_name())

        config = Configuration()
        prefix = config.prefix
        repository_cache = os.path.join(prefix, "LOCAL-REPO")
        r_output = output_template.format(prefix=os.path.normpath(prefix),
                                          repository_cache=repository_cache)

        with mock_print() as m:
            print_config(config, Session(DummyAuthenticator(), self.prefix))
            self.assertMultiLineEqual(m.value, r_output)

    def test_simple(self):
        output_template = textwrap.dedent("""\
            Python version: {pyver}
            enstaller version: {version}
            sys.prefix: {sys_prefix}
            platform: {platform}
            architecture: {arch}
            use_webservice: True
            config file: {{config_file}}
            keyring backend: {keyring_backend}
            settings:
                prefix = {{prefix}}
                repository_cache = {{repository_cache}}
                noapp = False
                proxy = None
            No valid auth information in configuration, cannot authenticate.
            You are not logged in.  To log in, type 'enpkg --userpass'.
        """).format(pyver=PY_VER, sys_prefix=os.path.normpath(sys.prefix),
                    version=__version__, platform=platform.platform(),
                    arch=platform.architecture()[0],
                    keyring_backend=_keyring_backend_name())

        try:
            with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
                fp.write("")
            config = Configuration.from_file(fp.name)
        finally:
            os.unlink(fp.name)

        prefix = config.prefix
        repository_cache = os.path.join(prefix, "LOCAL-REPO")
        r_output = output_template.format(prefix=os.path.normpath(prefix),
                                          config_file=fp.name,
                                          repository_cache=repository_cache)

        with mock_print() as m:
            print_config(config, Session(DummyAuthenticator(), self.prefix))
            self.assertMultiLineEqual(m.value, r_output)

    def test_simple_no_webservice(self):
        output_template = textwrap.dedent("""\
            Python version: {pyver}
            enstaller version: {version}
            sys.prefix: {sys_prefix}
            platform: {platform}
            architecture: {arch}
            use_webservice: False
            keyring backend: {keyring_backend}
            settings:
                prefix = {{prefix}}
                repository_cache = {{repository_cache}}
                noapp = False
                proxy = None
                IndexedRepos:
                    'http://acme.com/'
            No valid auth information in configuration, cannot authenticate.
            You are not logged in.  To log in, type 'enpkg --userpass'.
        """).format(pyver=PY_VER, sys_prefix=os.path.normpath(sys.prefix),
                    version=__version__, platform=platform.platform(),
                    arch=platform.architecture()[0],
                    keyring_backend=_keyring_backend_name())

        prefix = os.path.normpath(sys.prefix)
        repository_cache = os.path.join(prefix, "LOCAL-REPO")
        r_output = output_template.format(prefix=os.path.normpath(prefix),
                                          repository_cache=repository_cache)

        config = Configuration()
        config.update(indexed_repositories=["http://acme.com"],
                      use_webservice=False)

        with mock_print() as m:
            print_config(config, Session(DummyAuthenticator(), self.prefix))
            self.assertMultiLineEqual(m.value, r_output)


class TestConfiguration(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def assertSamePath(self, left, right):
        """Very naive implementation of path comparison."""
        if sys.platform == "win32":
            self.assertEqual(left.lower(), right.lower())
        else:
            self.assertEqual(left, right)

    def test_unsupported_syntax(self):
        # Given
        data = textwrap.dedent("""\
        store_url = 'http://acme'
        store_url += '.com'
        """)
        r_message = "Could not parse configuration file (error at line 2: " \
            "expression \"store_url += '.com'\" not supported)"

        # When
        with self.assertRaises(InvalidConfiguration) as e:
            Configuration.from_file(StringIO(data))

        # Then
        self.assertMultiLineEqual(str(e.exception), r_message)

    def test_invalid_syntax(self):
        # Given
        data = "store_url = http://acme.com"
        r_message = "Could not parse configuration file (invalid python " \
                    "syntax at line 1: expression 'store_url = " \
                    "http://acme.com')"

        # When
        with self.assertRaises(InvalidConfiguration) as e:
            Configuration.from_file(StringIO(data))

        # Then
        self.assertMultiLineEqual(str(e.exception), r_message)

    def test_proxy_setup(self):
        # Given
        proxy_string = "http://acme.com"

        # When
        config = Configuration()
        config.update(proxy=proxy_string)

        # Then
        self.assertEqual(str(config.proxy), "http://acme.com:3128")

    def test_verify_ssl_setup(self):
        # When
        config = Configuration()

        # Then
        self.assertTrue(config.verify_ssl)

        # Given
        data = StringIO("verify_ssl = True")

        # When
        config = Configuration.from_file(data)

        # Then
        self.assertTrue(config.verify_ssl)

        # Given
        data = StringIO("verify_ssl = False")

        # When
        config = Configuration.from_file(data)

        # Then
        self.assertFalse(config.verify_ssl)

    def test_max_retries_setup(self):
        # When
        config = Configuration()

        # Then
        self.assertEqual(config.max_retries, 0)

        # Given
        data = StringIO("max_retries = 1")

        # When
        config = Configuration.from_file(data)

        # Then
        self.assertEqual(config.max_retries, 1)

        # Given
        data = StringIO("max_retries = 0")

        # When
        config = Configuration.from_file(data)

        # Then
        self.assertEqual(config.max_retries, 0)

        # Given
        data = StringIO("max_retries = 'a'")

        # When/Then
        with self.assertRaises(InvalidConfiguration):
            Configuration.from_file(data)

    def test_parse_simple_unsupported_entry(self):
        # XXX: ideally, we would like to check for the warning, but doing so is
        # a bit too painful as it has not been backported to unittest2
        Configuration.from_file(StringIO("nono = 'le petit robot'"))

    def test__from_legacy_locations_simple(self):
        # Given
        default_config_file = os.path.join(self.prefix, ".enstaller4rc")
        with open(default_config_file, "w") as fp:
            fp.write("store_url = \"http://acme.com\"")

        # When
        with mock.patch("enstaller.config.legacy_configuration_read_search_order",
                        return_value=[self.prefix]):
            config = Configuration._from_legacy_locations()

        # Then
        self.assertEqual(config.store_url, "http://acme.com")

    def test__from_legacy_locations_non_existing_path(self):
        # When/Then
        with mock.patch("enstaller.config.legacy_configuration_read_search_order",
                        return_value=[self.prefix]):
            with self.assertRaises(InvalidConfiguration):
                Configuration._from_legacy_locations()

    def test_reset_auth_with_keyring(self):
        with make_keyring_available_context():
            config = Configuration()
            config.update(auth=(FAKE_USER, FAKE_PASSWORD))

            config.reset_auth()

            self.assertIsNone(config.auth)

    def test_set_prefix(self):
        homedir = os.path.normpath(os.path.expanduser("~"))

        config = Configuration()
        config.update(prefix=os.path.normpath("~/.env"))

        self.assertEqual(config.prefix, os.path.join(homedir, ".env"))

    def test_set_repository_cache(self):
        homedir = os.path.normpath(os.path.expanduser("~"))

        config = Configuration()
        config.update(repository_cache="~/.env/LOCAL-REPO")
        self.assertEqual(config.repository_cache, os.path.join(homedir, ".env", "LOCAL-REPO"))

    def test_set_epd_auth(self):
        config = Configuration()
        config.set_auth_from_encoded(FAKE_CREDS)

        self.assertEqual(config.auth, FAKE_AUTH)

    def test_set_invalid_epd_auth(self):
        config = Configuration()

        with self.assertRaises(InvalidConfiguration):
            config.set_auth_from_encoded(FAKE_USER)

    def test_write_default_config_simple(self):
        # Given
        path = os.path.join(self.prefix, ".enstaller4rc")

        # When
        write_default_config(path)

        # Then
        self.assertTrue(os.path.exists(path))

    def test_write_default_config_already_exists(self):
        # Given
        path = os.path.join(self.prefix, ".enstaller4rc")
        with open(path, "w") as fp:
            fp.write("")

        # When/Then
        with self.assertRaises(EnstallerException):
            write_default_config(path)

    def test_indices_property(self):
        # Given
        r_indices = tuple([
            ("https://api.enthought.com/eggs/{0}/index.json?pypi=true".
             format(custom_plat),
             "https://api.enthought.com/eggs/{0}/index.json".format(custom_plat)),
        ])
        config = Configuration()

        # When/Then
        self.assertEqual(config.indices, r_indices)

    def test_indices_property_platform(self):
        # Given
        platform = "win-32"
        r_indices = tuple([
            ("https://api.enthought.com/eggs/{0}/index.json?pypi=true".
             format(platform),
             "https://api.enthought.com/eggs/{0}/index.json".format(platform)),
        ])

        # When
        config = Configuration()
        config._platform = platform

        # Then
        self.assertEqual(config.indices, r_indices)

        # Given
        platform = "osx-32"
        r_indices = tuple([
            ("https://api.enthought.com/eggs/{0}/index.json?pypi=true".
             format(platform),
             "https://api.enthought.com/eggs/{0}/index.json".format(platform)),
        ])

        # When
        config = Configuration()
        config._platform = "osx-32"

        # Then
        self.assertEqual(config.indices, r_indices)

    def test_indices_property_no_pypi(self):
        # Given
        r_indices = tuple([
            ("https://api.enthought.com/eggs/{0}/index.json?pypi=false".
             format(custom_plat),
             "https://api.enthought.com/eggs/{0}/index.json".format(custom_plat)),
        ])
        config = Configuration()
        config.update(use_pypi=False)

        # When/Then
        self.assertEqual(config.indices, r_indices)

    def test_indices_property_no_webservice(self):
        # Given
        r_indices = tuple((
            ("https://acme.com/{0}/index.json".format(custom_plat),
             "https://acme.com/{0}/index.json".format(custom_plat)),
        ))
        config = Configuration()
        config.update(use_webservice=False,
                      indexed_repositories=["https://acme.com/{PLATFORM}/"])

        # When/Then
        self.assertEqual(config.indices, r_indices)

    def test_from_file_complete_combination1(self):
        # Given
        if sys.platform == "win32":
            r_prefix = "C:\\tmp"
        else:
            r_prefix = "/tmp"
        r_repository_cache = r_prefix
        fp = StringIO(textwrap.dedent("""\
        EPD_auth = "{creds}"

        repository_cache = {prefix!r}
        prefix = {prefix!r}
        use_webservice = True

        store_url = "http://acme.com"
        use_pypi = False
        autoupdate = False
        noapp = False
        """.format(creds=FAKE_CREDS, prefix=r_prefix)))

        # When
        config = Configuration.from_file(fp)

        # Then
        self.assertEqual(config.auth, FAKE_AUTH)
        self.assertSamePath(config.repository_cache, r_repository_cache)
        self.assertSamePath(config.prefix, r_prefix)
        self.assertEqual(config.use_webservice, True)
        self.assertEqual(config.store_url, "http://acme.com")
        self.assertEqual(config.use_pypi, False)
        self.assertEqual(config.autoupdate, False)
        self.assertEqual(config.noapp, False)

    def test_from_file_complete_combination2(self):
        # Given
        if sys.platform == "win32":
            r_prefix = "C:\\tmp"
        else:
            r_prefix = "/tmp"
        r_repository_cache = r_prefix
        fp = StringIO(textwrap.dedent("""\
        EPD_auth = "{creds}"

        repository_cache = {prefix!r}
        prefix = {prefix!r}
        use_webservice = False

        store_url = "http://acme.com"
        use_pypi = True
        autoupdate = True
        noapp = True
        """.format(creds=FAKE_CREDS, prefix=r_prefix)))

        # When
        config = Configuration.from_file(fp)

        # Then
        self.assertEqual(config.auth, FAKE_AUTH)
        self.assertSamePath(config.repository_cache, r_repository_cache)
        self.assertSamePath(config.prefix, r_prefix)
        self.assertEqual(config.use_webservice, False)
        self.assertEqual(config.store_url, "http://acme.com")
        self.assertEqual(config.use_pypi, True)
        self.assertEqual(config.autoupdate, True)
        self.assertEqual(config.noapp, True)

    def test_setup_in_init(self):
        # Given
        store_url = "acme.com"
        max_retries = 5

        # When
        config = Configuration(store_url=store_url, max_retries=max_retries)

        # Then
        self.assertEqual(config.max_retries, max_retries)
        self.assertEqual(config.store_url, store_url)

    def test_repository_cache(self):
        # Given no value supplied, default prefix

        # When
        config = Configuration()

        # Then
        self.assertEqual(config.repository_cache,
                         os.path.normpath(os.path.join(sys.prefix,
                                                       "LOCAL-REPO")))

        # Given a prefix, but no value supplied
        prefix = self.prefix

        # When
        config = Configuration(prefix=prefix)

        # Then
        self.assertEqual(config.repository_cache, os.path.join(prefix, "LOCAL-REPO"))

        # Given a value
        repository_cache = os.path.join(self.prefix, "mycache")

        # When
        config = Configuration(repository_cache=repository_cache)

        # Then
        self.assertEqual(config.repository_cache, repository_cache)


class TestMisc(unittest.TestCase):
    def test_writable_repository_cache(self):
        config = Configuration()
        with mkdtemp() as d:
            config.update(repository_cache=d)
            self.assertEqual(config.repository_cache, d)

    def test_non_writable_repository_cache(self):
        fake_dir = "/some/dummy_dir/hopefully/doesnt/exists"

        config = Configuration()

        with mock.patch("os.makedirs", side_effect=OSError("mocked makedirs")):
            config.update(repository_cache=fake_dir)
            self.assertNotEqual(config.repository_cache, fake_dir)


class TestPrependUrl(unittest.TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False, mode="wt") as fp:
            pass

        self.filename = fp.name

    def tearDown(self):
        os.unlink(self.filename)

    def test_simple(self):
        r_output = textwrap.dedent("""\
            IndexedRepos = [
              'url1',
              'url2',
              'url3',
            ]
        """)

        content = textwrap.dedent("""\
            IndexedRepos = [
              'url2',
              'url3',
            ]
        """)
        with open(self.filename, "w") as fp:
            fp.write(content)

        prepend_url(self.filename, "url1")
        with open(self.filename, "r") as fp:
            self.assertMultiLineEqual(fp.read(), r_output)

    def test_invalid(self):
        content = textwrap.dedent("""\
            #IndexedRepos = [
            #  'url1',
            #]
        """)
        with open(self.filename, "w") as fp:
            fp.write(content)

        with self.assertRaises(SystemExit):
            prepend_url(self.filename, "url1")


class TestYamlConfiguration(unittest.TestCase):
    def test_default(self):
        # Given/When
        config = Configuration.from_yaml_filename(StringIO(""))

        # Then
        self.assertFalse(config.use_webservice)
        self.assertFalse(config.indices, [])
        self.assertEqual(config.repository_cache,
                         os.path.normpath(os.path.join(sys.prefix,
                                                       "LOCAL-REPO")))
        self.assertEqual(config.store_kind, "brood")

    def test_invalid_format(self):
        # Given
        yaml_string = textwrap.dedent("""\
            repositoriess:
              - enthought/commercial
        """)

        # When/Then
        with self.assertRaises(InvalidConfiguration):
            Configuration.from_yaml_filename(StringIO(yaml_string))

    def test_load_from_path(self):
        # Given
        yaml_string = textwrap.dedent("""\
            repositories:
              - enthought/free
              - enthought/commercial
        """)
        platform = custom_plat
        r_indices = tuple((
            ('https://api.enthought.com/repo/enthought/free/{0}/index.json'.format(platform),
             'https://api.enthought.com/repo/enthought/free/{0}/index.json'.format(platform)),
            ('https://api.enthought.com/repo/enthought/commercial/{0}/index.json'.format(platform),
             'https://api.enthought.com/repo/enthought/commercial/{0}/index.json'.format(platform))
        ))

        with mkdtemp() as prefix:
            path = os.path.join(prefix, "enstaller.yaml")
            with open(path, "wt") as fp:
                fp.write(yaml_string)

            # When
            config = Configuration.from_yaml_filename(path)

            # Then
            self.assertFalse(config.use_webservice)
            self.assertEqual(config.store_url, "https://api.enthought.com")
            self.assertEqual(config.indices, r_indices)

    def test_simple(self):
        # Given
        yaml_string = textwrap.dedent("""\
            store_url: "http://acme.com"

            repositories:
              - enthought/free
              - enthought/commercial
        """)
        platform = custom_plat
        r_indices = tuple((
            ('http://acme.com/repo/enthought/free/{0}/index.json'.format(platform),
             'http://acme.com/repo/enthought/free/{0}/index.json'.format(platform)),
            ('http://acme.com/repo/enthought/commercial/{0}/index.json'.format(platform),
             'http://acme.com/repo/enthought/commercial/{0}/index.json'.format(platform))
        ))

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertFalse(config.use_webservice)
        self.assertEqual(config.store_url, "http://acme.com")
        self.assertEqual(config.indices, r_indices)
        self.assertEqual(config.max_retries, 0)
        self.assertTrue(config.verify_ssl)

    def test_api_token_authentication(self):
        # Given
        yaml_string = textwrap.dedent("""\
            authentication:
              kind: token
              api_token: ulysse
        """)

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertFalse(config.use_webservice)
        self.assertEqual(config.auth, APITokenAuth("ulysse"))

        # Given
        yaml_string = textwrap.dedent("""\
            authentication:
              api_token: ulysse
        """)

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertFalse(config.use_webservice)
        self.assertEqual(config.auth, APITokenAuth("ulysse"))

    def test_simple_authentication(self):
        # Given
        yaml_string = textwrap.dedent("""\
            authentication:
              kind: simple
              username: nono@acme.com
              password: ulysse
        """)

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertFalse(config.use_webservice)
        self.assertEqual(config.auth,
                         UserPasswordAuth("nono@acme.com", "ulysse"))

    def test_basic_authentication(self):
        # Given
        yaml_string = textwrap.dedent("""\
            authentication:
              kind: basic
              auth: {0}
        """.format(UserPasswordAuth("nono@acme.com", "ulysse")._encoded_auth))

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertFalse(config.use_webservice)
        self.assertEqual(config.auth,
                         UserPasswordAuth("nono@acme.com", "ulysse"))

    def test_files_cache(self):
        # Given
        yaml_string = textwrap.dedent("""\
            files_cache: "/foo/bar"
        """)

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertFalse(config.use_webservice)
        self.assertEqual(config.repository_cache, "/foo/bar")

        # Given
        yaml_string = textwrap.dedent("""\
            files_cache: "~/foo/bar/{PLATFORM}"
        """)

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertFalse(config.use_webservice)
        self.assertEqual(config.repository_cache,
                         os.path.expanduser("~/foo/bar/{0}".format(custom_plat)))

    def test_max_retries(self):
        # Given
        yaml_string = textwrap.dedent("""\
            max_retries: 1
        """)

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertEqual(config.max_retries, 1)

    def test_verify_ssl(self):
        # Given
        yaml_string = textwrap.dedent("""\
            verify_ssl: True
        """)

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertTrue(config.verify_ssl)

        # Given
        yaml_string = textwrap.dedent("""\
            verify_ssl: False
        """)

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertFalse(config.verify_ssl)

    def test_repositories(self):
        # Given
        yaml_string = textwrap.dedent("""\
            store_url: "http://www.acme.com"

            repositories:
              - "enthought/free"
              - "file:///foo"
        """)
        r_repositories = (
            "http://www.acme.com/repo/enthought/free/{0}/".format(custom_plat),
            "file:///foo/".format(custom_plat),
        )

        # When
        config = Configuration.from_yaml_filename(StringIO(yaml_string))

        # Then
        self.assertEqual(config.indexed_repositories, r_repositories)
