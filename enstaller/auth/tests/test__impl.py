from egginst._compat import TestCase

from enstaller.errors import InvalidConfiguration
from .._impl import UserPasswordAuth, _encode_string_base64


FAKE_USER = "john.doe"
FAKE_PASSWORD = "fake_password"
FAKE_AUTH = UserPasswordAuth(FAKE_USER, FAKE_PASSWORD)
FAKE_CREDS = FAKE_AUTH._encoded_auth


class TestUserPasswordAuth(TestCase):
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
