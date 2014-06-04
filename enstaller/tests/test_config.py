import base64
import contextlib
import os.path
import platform
import shutil
import sys
import tempfile
import textwrap

from cStringIO import StringIO

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from egginst.tests.common import mkdtemp

from enstaller.plat import custom_plat

from enstaller import __version__

from enstaller.config import (abs_expanduser,
    configuration_read_search_order, get_auth, get_path,
    input_auth, prepend_url, print_config, _is_using_epd_username,
    convert_auth_if_required, _keyring_backend_name)
from enstaller.config import (
    HOME_ENSTALLER4RC, KEYRING_SERVICE_NAME, SYS_PREFIX_ENSTALLER4RC,
    Configuration, add_url)
from enstaller.errors import InvalidConfiguration
from enstaller.utils import PY_VER

from .common import (make_keyring_available_context, make_keyring_unavailable,
                     mock_print, fake_keyring_context, fake_keyring)

def compute_creds(username, password):
    return "{0}:{1}".format(username, password).encode("base64").rstrip()

FAKE_USER = "john.doe"
FAKE_PASSWORD = "fake_password"
FAKE_CREDS = compute_creds(FAKE_USER, FAKE_PASSWORD)


@contextlib.contextmanager
def mock_default_filename_context(ret):
    with mock.patch("enstaller.config.Configuration._default_filename") as m:
        m.configure_mock(**{"return_value": ret})
        yield m


class TestGetPath(unittest.TestCase):
    def test_home_config_exists(self):
        home_dir = abs_expanduser("~")
        def mocked_isfile(p):
            if os.path.dirname(p) == home_dir:
                return True
            else:
                return os.path.isfile(p)

        with mock.patch("enstaller.config.isfile", mocked_isfile):
            self.assertEqual(get_path(), HOME_ENSTALLER4RC)

    def test_home_config_doesnt_exist(self):
        def mocked_isfile(p):
            if p == HOME_ENSTALLER4RC:
                return False
            elif p == SYS_PREFIX_ENSTALLER4RC:
                return True
            else:
                return os.path.isfile(p)

        with mock.patch("enstaller.config.isfile", mocked_isfile):
            self.assertEqual(get_path(), SYS_PREFIX_ENSTALLER4RC)

    def test_no_config(self):
        def mocked_isfile(p):
            if os.path.dirname(p) in configuration_read_search_order():
                return False
            else:
                return os.path.isfile(p)

        with mock.patch("enstaller.config.isfile", mocked_isfile):
            self.assertEqual(get_path(), None)

class TestInputAuth(unittest.TestCase):
    @mock.patch("enstaller.config.getpass", lambda ignored: FAKE_PASSWORD)
    def test_simple(self):
        with mock.patch("__builtin__.raw_input", lambda ignored: FAKE_USER):
            self.assertEqual(input_auth(), (FAKE_USER, FAKE_PASSWORD))

    @mock.patch("enstaller.config.getpass", lambda ignored: FAKE_PASSWORD)
    def test_empty(self):
        with mock.patch("__builtin__.raw_input", lambda ignored: ""):
            self.assertEqual(input_auth(), (None, None))

class TestWriteConfig(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, ".enstaller4rc")

    def tearDown(self):
        shutil.rmtree(self.d)

    @make_keyring_unavailable
    def test_simple(self):
        config = Configuration()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)
        config.write(self.f)

        config = Configuration.from_file(self.f)

        self.assertEqual(config.EPD_auth, FAKE_CREDS)
        self.assertEqual(config.autoupdate, True)
        self.assertEqual(config.proxy, None)
        self.assertEqual(config.use_webservice, True)
        self.assertEqual(config.webservice_entry_point,
                         "https://api.enthought.com/eggs/{0}/".format(custom_plat))
        self.assertEqual(config.api_url,
                         "https://api.enthought.com/accounts/user/info/")

    @make_keyring_unavailable
    def test_simple_with_proxy(self):
        proxystr = "http://acme.com:3128"

        config = Configuration()
        config.proxy = proxystr
        config.write(self.f)

        config = Configuration.from_file(self.f)
        self.assertEqual(config.proxy, proxystr)

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
            self.assertRegexpMatches(data, "http://acme.com")

    @make_keyring_unavailable
    def test_change_store_url(self):
        config = Configuration()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)
        config.write(self.f)

        config = Configuration.from_file(self.f)
        config.store_url = "https://acme.com"

        self.assertEqual(config.EPD_auth, FAKE_CREDS)
        self.assertEqual(config.autoupdate, True)
        self.assertEqual(config.proxy, None)
        self.assertEqual(config.use_webservice, True)
        self.assertEqual(config.webservice_entry_point,
                         "https://acme.com/eggs/{0}/".format(custom_plat))
        self.assertEqual(config.api_url,
                         "https://acme.com/accounts/user/info/")

class TestConfigKeyringConversion(unittest.TestCase):
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
        old_config = "EPD_auth = '{0}'".format(FAKE_CREDS)

        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write(old_config)
            filename = fp.name

        self.assertFalse(convert_auth_if_required(filename))

    @fake_keyring
    def test_username_to_auth_conversion(self):
        """
        Ensure we don't convert EPD_auth to using keyring.
        """
        # Given
        old_config = "EPD_username = '{0}'".format(FAKE_USER)
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write(old_config)
            filename = fp.name
        with fake_keyring_context() as mocked_keyring:
            mocked_keyring.set_password(KEYRING_SERVICE_NAME, FAKE_USER,
                                        FAKE_PASSWORD)

            # When
            converted = convert_auth_if_required(filename)

            # Then
            self.assertTrue(converted)
            with open(filename) as fp:
                self.assertMultiLineEqual(fp.read(), "EPD_auth = '{0}'".format(FAKE_CREDS))

class TestGetAuth(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, ".enstaller4rc")

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_with_keyring(self):
        with make_keyring_available_context() as mocked_keyring:
            config = Configuration()
            config.set_auth(FAKE_USER, FAKE_PASSWORD)

            self.assertEqual(config.get_auth(), (FAKE_USER, FAKE_PASSWORD))
            self.assertFalse(mocked_keyring.set_password.called)

    @make_keyring_unavailable
    def test_with_auth(self):
        config = Configuration()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)

        self.assertEqual(config.get_auth(), (FAKE_USER, FAKE_PASSWORD))

    def test_with_auth_and_keyring(self):
        with open(self.f, "w") as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))
        config = Configuration.from_file(self.f)

        attrs = {"get_password.return_value": FAKE_PASSWORD}
        mocked_keyring = mock.Mock(**attrs)
        with mock.patch("enstaller.config.keyring", mocked_keyring):
            config.EPD_username = FAKE_USER

            self.assertFalse(mocked_keyring.get_password.called)
            self.assertEqual(config.get_auth(), (FAKE_USER, FAKE_PASSWORD))

    @make_keyring_unavailable
    def test_without_auth_or_keyring(self):
        config = Configuration()
        self.assertEqual(config.get_auth(), (None, None))

    @make_keyring_unavailable
    def test_deprecated_get_auth(self):
        with mkdtemp() as d:
            f = os.path.join(d, "enstaller4rc")
            config = Configuration()
            config.set_auth(FAKE_USER, FAKE_PASSWORD)
            config.write(f)

            with mock.patch("enstaller.config.get_path", lambda: f):
                self.assertEqual(get_auth(), (FAKE_USER, FAKE_PASSWORD))

    def test_without_existing_configuration(self):
        with mock.patch("enstaller.config.get_path", lambda: None):
            with self.assertRaises(InvalidConfiguration):
                get_auth()

class TestWriteAndChangeAuth(unittest.TestCase):
    @make_keyring_unavailable
    def test_change_existing_config_file(self):
        r_new_password = "ouioui_dans_sa_petite_voiture"
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        config = Configuration.from_file(fp.name)
        self.assertEqual(config.get_auth(), (FAKE_USER, FAKE_PASSWORD))

        config.set_auth(FAKE_USER, r_new_password)
        config._change_auth(fp.name)
        new_config = Configuration.from_file(fp.name)

        self.assertEqual(new_config.get_auth(), (FAKE_USER, r_new_password))

    @make_keyring_unavailable
    def test_change_existing_config_file_empty_username(self):
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        config = Configuration.from_file(fp.name)
        self.assertEqual(config.get_auth(), (FAKE_USER, FAKE_PASSWORD))

        config.reset_auth()
        config._change_auth(fp.name)

        new_config = Configuration.from_file(fp.name)
        self.assertEqual(new_config.get_auth(), (None, None))

    def test_change_existing_config_file_without_keyring(self):
        # Given
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        # When
        config = Configuration.from_file(fp.name)
        config.set_auth("user", "dummy")
        config._change_auth(fp.name)

        # Then
        with open(fp.name, "r") as f:
            content = f.read()
            self.assertNotRegexpMatches(content, "EPD_username")
            self.assertRegexpMatches(content, "EPD_auth")
        config = Configuration.from_file(fp.name)
        self.assertEqual(config.get_auth(), ("user", "dummy"))

    @make_keyring_unavailable
    def test_change_empty_config_file_empty_username(self):
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write("")

        config = Configuration.from_file(fp.name)
        self.assertEqual(config.get_auth(), (None, None))

        config.set_auth(FAKE_USER, FAKE_PASSWORD)
        self.assertEqual(config.get_auth(), (FAKE_USER, FAKE_PASSWORD))

    @make_keyring_unavailable
    def test_no_config_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write("")

        config = Configuration()
        self.assertEqual(config.get_auth(), (None, None))

        config.set_auth(FAKE_USER, FAKE_PASSWORD)
        config.write(fp.name)

        new_config = Configuration.from_file(fp.name)
        self.assertEqual(new_config.get_auth(), (FAKE_USER, FAKE_PASSWORD))

    @make_keyring_unavailable
    def test_change_auth_wo_existing_auth(self):
        r_output = "EPD_auth = '{0}'\n".format(FAKE_CREDS)

        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write("")

        config = Configuration.from_file(fp.name)
        config.set_auth(FAKE_USER, FAKE_PASSWORD)
        config._change_auth(fp.name)

        with open(fp.name) as fp:
            self.assertMultiLineEqual(fp.read(), r_output)

    # FIXME: do we really want to revert the behaviour of change_auth() with
    # auth == (None, None) to do nothing ?
    @unittest.expectedFailure
    @make_keyring_unavailable
    def test_change_config_file_empty_auth(self):
        config_data = "EPD_auth = '{0}'".format(FAKE_CREDS)
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write(config_data)

        config = Configuration.from_file(fp.name)
        config.set_auth(None, None)
        config._change_auth(fp.name)

        with open(fp.name, "r") as fp:
            self.assertEqual(fp.read(), config_data)

class TestAuthenticationConfiguration(unittest.TestCase):
    @make_keyring_unavailable
    def test_without_configuration_no_keyring(self):
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write("")

        config = Configuration.from_file(fp.name)
        self.assertFalse(config.is_auth_configured)

    def test_without_configuration_with_keyring(self):
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write("")

        with mock.patch("enstaller.config.keyring"):
            config = Configuration.from_file(fp.name)
            self.assertFalse(config.is_auth_configured)

    @make_keyring_unavailable
    def test_with_configuration_no_keyring(self):
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            auth_line = "EPD_auth = '{0}'".format(FAKE_CREDS)
            fp.write(auth_line)

        config = Configuration.from_file(fp.name)
        self.assertTrue(config.is_auth_configured)

    def test_with_configuration_with_keyring(self):
        with tempfile.NamedTemporaryFile(delete=False) as fp:
            auth_line = "EPD_username = '{0}'".format(FAKE_USER)
            fp.write(auth_line)

        mocked_keyring = mock.Mock(["get_password"])
        with mock.patch("enstaller.config.keyring", mocked_keyring):
            config = Configuration.from_file(fp.name)
            self.assertTrue(config.is_auth_configured)

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
        self.assertEqual(config.EPD_auth, FAKE_CREDS)
        self.assertEqual(config.EPD_username, FAKE_USER)

    @make_keyring_unavailable
    def test_epd_invalid_auth(self):
        s = StringIO("EPD_auth = '{0}'".format(base64.encodestring(FAKE_USER).rstrip()))

        with self.assertRaises(InvalidConfiguration):
            Configuration.from_file(s)

    @make_keyring_unavailable
    def test_epd_username_wo_keyring(self):
        """
        Ensure config auth correctly reports itself as non configured when
        using EPD_auth but keyring is not available to get password.
        """
        s = StringIO("EPD_username = '{0}'".format(FAKE_USER))

        config = Configuration.from_file(s)
        self.assertFalse(config.is_auth_configured)
        with self.assertRaises(InvalidConfiguration):
            config.EPD_auth

    def test_epd_username(self):
        with fake_keyring_context() as mocked_keyring:
            mocked_keyring.set_password(KEYRING_SERVICE_NAME, FAKE_USER, FAKE_PASSWORD)

            s = StringIO("EPD_username = '{0}'".format(FAKE_USER))
            config = Configuration.from_file(s)

            self.assertEqual(config.EPD_username, FAKE_USER)
            self.assertEqual(config.EPD_auth, FAKE_CREDS)

    def test_epd_auth(self):
        """
        Ensure config auth information is properly set-up when using EPD_auth
        """
        s = StringIO("EPD_auth = '{0}'".format(FAKE_CREDS))
        config = Configuration.from_file(s)

        self.assertEqual(config.EPD_username, FAKE_USER)
        self.assertEqual(config.EPD_auth, FAKE_CREDS)

class TestConfigurationPrint(unittest.TestCase):
    maxDiff = None

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
                IndexedRepos: (not used)
            No valid auth information in configuration, cannot authenticate.
            You are not logged in.  To log in, type 'enpkg --userpass'.
        """).format(pyver=PY_VER, sys_prefix=sys.prefix, version=__version__,
                    platform=platform.platform(), arch=platform.architecture()[0],
                    keyring_backend=_keyring_backend_name())

        config = Configuration()
        prefix = config.prefix
        repository_cache = os.path.join(prefix, "LOCAL-REPO")
        r_output = output_template.format(prefix=prefix,
                                          repository_cache=repository_cache)

        with mock_print() as m:
            print_config(config, config.prefix)
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
                IndexedRepos: (not used)
            No valid auth information in configuration, cannot authenticate.
            You are not logged in.  To log in, type 'enpkg --userpass'.
        """).format(pyver=PY_VER, sys_prefix=sys.prefix, version=__version__,
                    platform=platform.platform(), arch=platform.architecture()[0],
                    keyring_backend=_keyring_backend_name())

        try:
            with tempfile.NamedTemporaryFile(delete=False) as fp:
                fp.write("")
            config = Configuration.from_file(fp.name)
        finally:
            os.unlink(fp.name)

        prefix = config.prefix
        repository_cache = os.path.join(prefix, "LOCAL-REPO")
        r_output = output_template.format(prefix=prefix, config_file=fp.name,
                                          repository_cache=repository_cache)

        with mock_print() as m:
            print_config(config, config.prefix)
            self.assertMultiLineEqual(m.value, r_output)

class TestConfiguration(unittest.TestCase):
    def test_parse_simple_unsupported_entry(self):
        # XXX: ideally, we would like to check for the warning, but doing so is
        # a bit too painful as it has not been backported to unittest2
        Configuration.from_file(StringIO("nono = 'le petit robot'"))

    def test_reset_auth_with_keyring(self):
        with make_keyring_available_context() as m:
            config = Configuration()
            config.set_auth(FAKE_USER, FAKE_PASSWORD)

            config.reset_auth()

            self.assertIsNone(config._username)
            self.assertIsNone(config._password)
            self.assertFalse(config.is_auth_configured)

    def test_set_prefix(self):
        homedir = os.path.normpath(os.path.expanduser("~"))

        config = Configuration()
        config.prefix = os.path.normpath("~/.env")

        self.assertEqual(config.prefix, os.path.join(homedir, ".env"))

    def test_set_repository_cache(self):
        homedir = os.path.normpath(os.path.expanduser("~"))

        config = Configuration()
        config.repository_cache = "~/.env/LOCAL-REPO"
        self.assertEqual(config.repository_cache, os.path.join(homedir, ".env", "LOCAL-REPO"))

    def test_set_epd_auth(self):
        config = Configuration()
        config.EPD_auth = FAKE_CREDS

        self.assertEqual(config._username, FAKE_USER)
        self.assertEqual(config._password, FAKE_PASSWORD)

    def test_set_invalid_epd_auth(self):
        config = Configuration()

        with self.assertRaises(InvalidConfiguration):
            config.EPD_auth = FAKE_USER

class TestMisc(unittest.TestCase):
    def test_writable_repository_cache(self):
        config = Configuration()
        with mkdtemp() as d:
            config.repository_cache = d
            self.assertEqual(config.repository_cache, d)

    def test_non_writable_repository_cache(self):
        fake_dir = "/some/dummy_dir/hopefully/doesnt/exists"

        config = Configuration()
        def mocked_makedirs(d):
            raise OSError("mocked makedirs")
        with mock.patch("os.makedirs", mocked_makedirs):
            config.repository_cache = fake_dir
            self.assertNotEqual(config.repository_cache, fake_dir)


class TestPrependUrl(unittest.TestCase):
    def setUp(self):
        with tempfile.NamedTemporaryFile(delete=False) as fp:
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
