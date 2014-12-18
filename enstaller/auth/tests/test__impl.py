import os
import shutil
import tempfile
import textwrap

from egginst.vendor.six.moves import unittest

from enstaller.errors import InvalidConfiguration
from enstaller.vendor import requests

from ..auth_managers import BroodBearerTokenAuth
from .._impl import APITokenAuth, UserPasswordAuth, _encode_string_base64


FAKE_USER = "john.doe"
FAKE_PASSWORD = "fake_password"
FAKE_AUTH = UserPasswordAuth(FAKE_USER, FAKE_PASSWORD)
FAKE_CREDS = FAKE_AUTH._encoded_auth


class TestUserPasswordAuth(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_from_encoded_auth(self):
        # Given
        auth_string = FAKE_CREDS
        auth_section = textwrap.dedent("""
        # A Canopy / EPD subscriber authentication is required to access the
        # Canopy / EPD repository.  To change your credentials, use the 'enpkg
        # --userpass' command, which will ask you for your email address
        # password.
        %s
        """ % ("EPD_auth = '{0}'".format(FAKE_CREDS)))

        # When
        auth = UserPasswordAuth.from_encoded_auth(auth_string)

        # Then
        self.assertEqual(auth.username, FAKE_USER)
        self.assertEqual(auth.password, FAKE_PASSWORD)
        self.assertMultiLineEqual(auth.config_string, auth_section)

    def test_invalid_from_encoded(self):
        # Given
        auth_string = _encode_string_base64("yopla")

        # When/Then
        with self.assertRaises(InvalidConfiguration):
            UserPasswordAuth.from_encoded_auth(auth_string)

    def test_empty_username(self):
        # Given
        username, password = "", ""

        # When/Then
        with self.assertRaises(InvalidConfiguration):
            UserPasswordAuth(username, password)

        # Given
        username, password = None, ""

        # When/Then
        with self.assertRaises(InvalidConfiguration):
            UserPasswordAuth(username, password)

        # Given
        username, password = "a", ""

        # When
        auth = UserPasswordAuth(username, password)

        # Then
        self.assertEqual(auth.username, "a")
        self.assertEqual(auth.password, "")

    def test_change_auth(self):
        # Given
        path = os.path.join(self.prefix, "enstaller.cfg")
        with open(path, "wt") as fp:
            fp.write("")

        auth = UserPasswordAuth("dummy", "auth")

        # When
        auth.change_auth(path)

        # Then
        with open(path) as fp:
            data = fp.read()
        self.assertEqual(data, "EPD_auth = '{0}'\n".format(auth._encoded_auth))

    def test_change_auth_existing(self):
        # Given
        auth = UserPasswordAuth("dummy", "auth")

        path = os.path.join(self.prefix, "enstaller.cfg")
        with open(path, "wt") as fp:
            fp.write("EPD_auth = '{0}'\n".format(auth._encoded_auth))

        # When
        auth = UserPasswordAuth("another_dummy", "auth")
        auth.change_auth(path)

        # Then
        with open(path) as fp:
            data = fp.read()
        self.assertEqual(data, "EPD_auth = '{0}'\n".format(auth._encoded_auth))

    def test_change_auth_with_api(self):
        # Given
        path = os.path.join(self.prefix, "enstaller.cfg")
        with open(path, "wt") as fp:
            fp.write("api_token = 'dummy_token'")

        auth = UserPasswordAuth("dummy", "auth")

        # When
        auth.change_auth(path)

        # Then
        with open(path) as fp:
            data = fp.read()
        self.assertEqual(data, "EPD_auth = '{0}'\n".format(auth._encoded_auth))

    def test_request_adapter(self):
        # Given
        auth = UserPasswordAuth("nono", "le petit robot")

        # When/Then
        self.assertIsInstance(auth.request_adapter, requests.auth.HTTPBasicAuth)
        self.assertEqual(auth.request_adapter.username, "nono")
        self.assertEqual(auth.request_adapter.password, "le petit robot")

    def test_cant_login_message(self):
        # Given
        r_message = "Could not authenticate as {0!r}".format("nono")

        # When
        auth = UserPasswordAuth("nono", "le petit robot")

        # Then
        self.assertEqual(auth.cant_login_message, r_message)


class TestAPITokenAuth(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_simple(self):
        # Given
        token = "dummy auth"

        # When
        auth = APITokenAuth(token)

        # Then
        self.assertEqual(auth.config_string,
                         "api_token = '{0}'".format(token))
        self.assertEqual(auth.logged_message,
                         "logged in using API token")

    def test_change_auth(self):
        # Given
        path = os.path.join(self.prefix, "enstaller.cfg")
        with open(path, "wt") as fp:
            fp.write("")

        auth = APITokenAuth("dummy auth")

        # When
        auth.change_auth(path)

        # Then
        with open(path) as fp:
            data = fp.read()
        self.assertEqual(data, "api_token = 'dummy auth'")

    def test_change_auth_existing(self):
        # Given
        path = os.path.join(self.prefix, "enstaller.cfg")
        with open(path, "wt") as fp:
            fp.write("api_token = 'yoyo'")

        auth = APITokenAuth("dummy auth")

        # When
        auth.change_auth(path)

        # Then
        with open(path) as fp:
            data = fp.read()
        self.assertEqual(data, "api_token = 'dummy auth'")

    def test_change_auth_with_epd_auth(self):
        # Given
        path = os.path.join(self.prefix, "enstaller.cfg")
        with open(path, "wt") as fp:
            fp.write("EPD_auth = 'dummy_token'")

        auth = APITokenAuth("dummy_token")

        # When
        auth.change_auth(path)

        # Then
        with open(path) as fp:
            data = fp.read()
        self.assertEqual(data, auth.config_string)

    def test_request_adapter(self):
        # Given
        auth = APITokenAuth("nono le petit robot")

        # When/Then
        self.assertIsInstance(auth.request_adapter, BroodBearerTokenAuth)
        self.assertEqual(auth.request_adapter._token, "nono le petit robot")

    def test_cant_login_message(self):
        # Given
        r_message = ("Could not authenticate with the given token: check "
                     "your token settings")

        # When
        auth = APITokenAuth("le petit robot")

        # Then
        self.assertEqual(auth.cant_login_message, r_message)
