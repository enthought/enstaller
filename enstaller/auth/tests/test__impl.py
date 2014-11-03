import os
import shutil
import tempfile

from egginst.vendor.six.moves import unittest

from enstaller.errors import InvalidConfiguration
from .._impl import APITokenAuth, UserPasswordAuth, _encode_string_base64


FAKE_USER = "john.doe"
FAKE_PASSWORD = "fake_password"
FAKE_AUTH = UserPasswordAuth(FAKE_USER, FAKE_PASSWORD)
FAKE_CREDS = FAKE_AUTH._encoded_auth


class TestUserPasswordAuth(unittest.TestCase):
    def test_from_encoded_auth(self):
        # Given
        auth_string = FAKE_CREDS

        # When
        auth = UserPasswordAuth.from_encoded_auth(auth_string)

        # Then
        self.assertEqual(auth.username, FAKE_USER)
        self.assertEqual(auth.password, FAKE_PASSWORD)

    def test_invalid_from_encoded(self):
        # Given
        auth_string = _encode_string_base64("yopla")

        # When/Then
        with self.assertRaises(InvalidConfiguration):
            UserPasswordAuth.from_encoded_auth(auth_string)


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
