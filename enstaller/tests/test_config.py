import base64
import contextlib
import json
import os.path
import platform
import shutil
import sys
import tempfile
import textwrap
import urllib2

from cStringIO import StringIO

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from egginst.tests.common import mkdtemp

from enstaller import __version__

from enstaller.config import (AuthFailedError, abs_expanduser, authenticate,
    configuration_read_search_order, get_auth, get_default_url, get_path,
    input_auth, prepend_url, print_config, subscription_level, web_auth)
from enstaller.config import (
    HOME_ENSTALLER4RC, KEYRING_SERVICE_NAME, SYS_PREFIX_ENSTALLER4RC,
    Configuration, PythonConfigurationParser)
from enstaller.errors import InvalidConfiguration, InvalidFormat
from enstaller.utils import PY_VER

from .common import (make_keyring_available_context, make_keyring_unavailable,
                     make_keyring_unavailable_context, mock_print,
                     )

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
        self.assertEqual(config.webservice_entry_point, get_default_url())

    @make_keyring_unavailable
    def test_simple_with_proxy(self):
        proxystr = "http://acme.com:3128"

        config = Configuration()
        config.proxy = proxystr
        config.write(self.f)

        config = Configuration.from_file(self.f)
        self.assertEqual(config.proxy, proxystr)

    def test_keyring_call(self):
        with mock.patch("__builtin__.open"):
            mocked_keyring = mock.MagicMock(["get_password", "set_password"])
            with mock.patch("enstaller.config.keyring", mocked_keyring):
                config = Configuration()
                config.set_auth(FAKE_USER, FAKE_PASSWORD)
                config.write("dummy_config.rc")

                r_args = ("Enthought.com", FAKE_USER, FAKE_PASSWORD)
                self.assertTrue(mocked_keyring.set_password.call_with(r_args))
                r_args = ("Enthought.com", FAKE_USER)
                self.assertTrue(mocked_keyring.get_password.call_with(r_args))


AUTH_API_URL = 'https://api.enthought.com/accounts/user/info/'

R_JSON_AUTH_RESP = {'first_name': u'David',
        'has_subscription': True,
        'is_active': True,
        'is_authenticated': True,
        'last_name': u'Cournapeau',
        'subscription_level': u'basic'}

R_JSON_NOAUTH_RESP = {'is_authenticated': False,
        'last_name': u'Cournapeau',
        'subscription_level': u'basic'}

class TestWebAuth(unittest.TestCase):
    def test_invalid_auth_args(self):
        with self.assertRaises(AuthFailedError):
            web_auth((None, None))

    def test_simple(self):
        with mock.patch("enstaller.config.urllib2") as murllib2:
            attrs = {'urlopen.return_value': StringIO(json.dumps(R_JSON_AUTH_RESP))}
            murllib2.configure_mock(**attrs)
            self.assertEqual(web_auth((FAKE_USER, FAKE_PASSWORD)),
                             R_JSON_AUTH_RESP)

    def test_auth_encoding(self):
        r_headers = {"Authorization": "Basic " + FAKE_CREDS}
        with mock.patch("enstaller.config.urllib2") as murllib2:
            attrs = {'urlopen.return_value': StringIO(json.dumps(R_JSON_AUTH_RESP))}
            murllib2.configure_mock(**attrs)

            web_auth((FAKE_USER, FAKE_PASSWORD))
            murllib2.Request.assert_called_with(AUTH_API_URL, headers=r_headers)

    def test_urllib_failures(self):
        with mock.patch("enstaller.config.urllib2") as murllib2:
            # XXX: we can't rely on mock for exceptions, but there has to be a
            # better way ?
            murllib2.URLError = urllib2.URLError

            attrs = {'urlopen.side_effect': urllib2.URLError("dummy")}
            murllib2.configure_mock(**attrs)

            with self.assertRaises(AuthFailedError):
                web_auth((FAKE_USER, FAKE_PASSWORD))

        with mock.patch("enstaller.config.urllib2") as murllib2:
            murllib2.HTTPError = urllib2.URLError

            mocked_fp = mock.MagicMock()
            mocked_fp.read.side_effect = murllib2.HTTPError("dummy")
            attrs = {'urlopen.return_value': mocked_fp}
            murllib2.configure_mock(**attrs)

            with self.assertRaises(AuthFailedError):
                web_auth((FAKE_USER, FAKE_PASSWORD))

    def test_unauthenticated_user(self):
        with mock.patch("enstaller.config.urllib2") as murllib2:
            attrs = {'urlopen.return_value': StringIO(json.dumps(R_JSON_NOAUTH_RESP))}
            murllib2.configure_mock(**attrs)

            with self.assertRaises(AuthFailedError):
                web_auth((FAKE_USER, FAKE_PASSWORD))

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
            mocked_keyring.set_password.assert_called_with("Enthought.com",
                                                           FAKE_USER,
                                                           FAKE_PASSWORD)

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

    def test_change_existing_config_file_with_keyring(self):
        r_output = "EPD_username = '{0}'".format(FAKE_USER)

        with tempfile.NamedTemporaryFile(delete=False) as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        with make_keyring_available_context() as mocked_keyring:
            config = Configuration.from_file(fp.name)
            config.set_auth("user", "dummy")
            config._change_auth(fp.name)

            mocked_keyring.set_password.assert_called_with("Enthought.com", "user", "dummy")

        with open(fp.name, "r") as f:
            self.assertRegexpMatches(f.read(), "EPD_username")
            self.assertNotRegexpMatches(f.read(), "EPD_auth")

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

class TestAuthenticate(unittest.TestCase):
    def test_use_webservice_valid_user(self):
        config = Configuration()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)

        with mock.patch("enstaller.config.web_auth") as mocked_auth:
            authenticate(config)
            self.assertTrue(mocked_auth.called)

    def test_use_webservice_invalid_user(self):
        config = Configuration()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)

        with mock.patch("enstaller.config.web_auth") as mocked_auth:
            mocked_auth.return_value = {"is_authenticated": False}

            with self.assertRaises(AuthFailedError):
                authenticate(config)

    def test_use_remote(self):
        config = Configuration()
        config.use_webservice = False
        config.set_auth(FAKE_USER, FAKE_PASSWORD)

        remote = mock.Mock()
        user = authenticate(config, remote)
        self.assertEqual(user, {"is_authenticated": True})

    def test_use_remote_invalid(self):
        config = Configuration()
        config.use_webservice = False
        config.set_auth(FAKE_USER, FAKE_PASSWORD)

        remote = mock.Mock()

        for klass in KeyError, Exception:
            attrs = {"connect.side_effect": klass()}
            remote.configure_mock(**attrs)

            with self.assertRaises(AuthFailedError):
                authenticate(config, remote)

class TestSubscriptionLevel(unittest.TestCase):
    def test_unsubscribed_user(self):
        user_info = {"is_authenticated": True}
        self.assertEqual(subscription_level(user_info), "EPD")

        user_info = {"is_authenticated": False}
        self.assertIsNone(subscription_level(user_info))

    def test_subscribed_user(self):
        user_info = {"has_subscription": True, "is_authenticated": True}
        self.assertEqual(subscription_level(user_info), "EPD Basic or above")

        user_info = {"has_subscription": False, "is_authenticated": True}
        self.assertEqual(subscription_level(user_info), "EPD Free")

        user_info = {"has_subscription": False, "is_authenticated": False}
        self.assertIsNone(subscription_level(user_info))

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
    def test_parse_simple(self):
        r_data = {"IndexedRepos": ["http://acme.com/{SUBDIR}"],
                  "webservice_entry_point": "http://acme.com/eggs/{PLATFORM}/"}

        s = textwrap.dedent("""\
        IndexedRepos = [
            "http://acme.com/{SUBDIR}",
        ]
        webservice_entry_point = "http://acme.com/eggs/{PLATFORM}/"
        """)

        data = PythonConfigurationParser().parse(s)
        self.assertEqual(data, r_data)

    def test_parse_simple_invalid_file(self):
        with self.assertRaises(InvalidFormat):
            PythonConfigurationParser().parse("EPD_auth = 1 + 2")

        with self.assertRaises(InvalidFormat):
            PythonConfigurationParser().parse("1 + 2")

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

    @mock.patch("enstaller.config.keyring")
    def test_epd_username_with_keyring(self, mocked_keyring):
        mocked_keyring.get_password = lambda service, username: FAKE_PASSWORD

        s = StringIO("EPD_username = '{0}'".format(FAKE_USER))
        config = Configuration.from_file(s)

        self.assertTrue(config.use_keyring)
        self.assertEqual(config.EPD_username, FAKE_USER)
        self.assertEqual(config.EPD_auth, FAKE_CREDS)

    @mock.patch("enstaller.config.keyring")
    def test_epd_auth_with_keyring(self, mocked_keyring):
        """
        Ensure config is properly setup in keyring mode when using EPD_auth
        """
        s = StringIO("EPD_auth = '{0}'".format(FAKE_CREDS))
        config = Configuration.from_file(s)

        self.assertTrue(config.use_keyring)
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
            settings:
                prefix = {{prefix}}
                local = {{local}}
                noapp = False
                proxy = None
                IndexedRepos: (not used)
            No valid auth information in configuration, cannot authenticate.
            You are not logged in.  To log in, type 'enpkg --userpass'.
        """).format(pyver=PY_VER, sys_prefix=sys.prefix, version=__version__,
                    platform=platform.platform(), arch=platform.architecture()[0])

        config = Configuration()
        prefix = config.prefix
        local = os.path.join(prefix, "LOCAL-REPO")
        r_output = output_template.format(prefix=prefix, local=local)

        with mock_print() as m:
            print_config(config, None, config.prefix)
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
            settings:
                prefix = {{prefix}}
                local = {{local}}
                noapp = False
                proxy = None
                IndexedRepos: (not used)
            No valid auth information in configuration, cannot authenticate.
            You are not logged in.  To log in, type 'enpkg --userpass'.
        """).format(pyver=PY_VER, sys_prefix=sys.prefix, version=__version__,
                    platform=platform.platform(), arch=platform.architecture()[0])

        try:
            with tempfile.NamedTemporaryFile(delete=False) as fp:
                fp.write("")
            config = Configuration.from_file(fp.name)
        finally:
            os.unlink(fp.name)

        prefix = config.prefix
        local = os.path.join(prefix, "LOCAL-REPO")
        r_output = output_template.format(prefix=prefix, config_file=fp.name, local=local)

        with mock_print() as m:
            print_config(config, None, config.prefix)
            self.assertMultiLineEqual(m.value, r_output)

class TestConfiguration(unittest.TestCase):
    def test_parse_simple_unsupported_entry(self):
        # XXX: ideally, we would like to check for the warning, but doing so is
        # a bit too painful as it has not been backported to unittest2
        Configuration.from_file(StringIO("nono = 'le petit robot'"))

    def test_keyring_argument(self):
        with make_keyring_unavailable_context():
            config = Configuration()
            self.assertFalse(config.use_keyring)

            config = Configuration(use_keyring=False)
            self.assertFalse(config.use_keyring)

            with self.assertRaises(InvalidConfiguration):
                config = Configuration(use_keyring=True)

        with make_keyring_available_context():
            config = Configuration()
            self.assertTrue(config.use_keyring)

            config = Configuration(use_keyring=True)
            self.assertTrue(config.use_keyring)

            config = Configuration(use_keyring=False)
            self.assertFalse(config.use_keyring)

    @make_keyring_unavailable
    def test_reset_auth_without_keyring(self):
        config = Configuration()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)

        config.reset_auth()

        self.assertIsNone(config._username)
        self.assertIsNone(config._password)
        self.assertFalse(config.is_auth_configured)

    def test_reset_auth_with_keyring(self):
        with make_keyring_available_context() as m:
            config = Configuration()
            config.set_auth(FAKE_USER, FAKE_PASSWORD)

            config.reset_auth()

            m.set_password.assert_called_with(KEYRING_SERVICE_NAME, FAKE_USER, "")
            self.assertIsNone(config._username)
            self.assertIsNone(config._password)
            self.assertTrue(config.use_keyring)
            self.assertFalse(config.is_auth_configured)

    def test_reset_auth_with_keyring_failure(self):
        """Ensure reset_auth failed with keyring if no user is set up."""
        with make_keyring_available_context():
            config = Configuration()

            with self.assertRaises(ValueError):
                config.reset_auth()

    def test_set_prefix(self):
        homedir = os.path.normpath(os.path.expanduser("~"))

        config = Configuration()
        config.prefix = os.path.normpath("~/.env")

        self.assertEqual(config.prefix, os.path.join(homedir, ".env"))

    def test_set_local(self):
        homedir = os.path.normpath(os.path.expanduser("~"))

        config = Configuration()
        config.local = os.path.normpath("~/.env/LOCAL-REPO")

        self.assertEqual(config.local, os.path.join(homedir, ".env", "LOCAL-REPO"))

    def test_set_epd_auth(self):
        config = Configuration()
        config.EPD_auth = FAKE_CREDS

        self.assertEqual(config._username, FAKE_USER)
        self.assertEqual(config._password, FAKE_PASSWORD)

    def test_set_invalid_epd_auth(self):
        config = Configuration()

        with self.assertRaises(InvalidConfiguration):
            config.EPD_auth = FAKE_USER

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
