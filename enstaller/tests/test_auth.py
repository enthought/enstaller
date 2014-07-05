import json
import os.path
import shutil
import sys
import tempfile

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from mock import patch

import enstaller.config

from enstaller.auth import _web_auth, DUMMY_USER, UserInfo, authenticate
from enstaller.config import Configuration, write_default_config
from enstaller.errors import (AuthFailedError, EnstallerException,
                              InvalidConfiguration)
from enstaller.tests.common import fake_keyring
from enstaller.vendor import requests, responses


basic_user = UserInfo(True, first_name="Jane", last_name="Doe", has_subscription=True)
free_user = UserInfo(True, first_name="John", last_name="Smith", has_subscription=False)
anon_user = UserInfo(False)
old_auth_user = DUMMY_USER

def compute_creds(username, password):
    return "{0}:{1}".format(username, password).encode("base64").rstrip()

AUTH_API_URL = 'https://api.enthought.com/accounts/user/info/'

FAKE_USER = "john.doe"
FAKE_PASSWORD = "fake_password"
FAKE_CREDS = compute_creds(FAKE_USER, FAKE_PASSWORD)

R_JSON_AUTH_RESP = {'first_name': u'David',
        'has_subscription': True,
        'is_active': True,
        'is_authenticated': True,
        'last_name': u'Cournapeau',
        'subscription_level': u'basic'}

R_JSON_NOAUTH_RESP = {'is_authenticated': False,
        'last_name': u'Cournapeau',
        'first_name': u'David',
        'has_subscription': True,
        'subscription_level': u'basic'}


@fake_keyring
class CheckedChangeAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, "enstaller4rc")

    def tearDown(self):
        shutil.rmtree(self.d)

    @patch('enstaller.config.authenticate', return_value=basic_user)
    def test_simple(self, mock1):
        config = Configuration()
        config.set_auth('usr', 'password')
        write_default_config(self.f)
        config._checked_change_auth(self.f)

        new_config = Configuration.from_file(self.f)
        usr = enstaller.config.authenticate(new_config)

        self.assertTrue(usr.is_authenticated)
        self.assertTrue(usr.has_subscription)

    def test_no_acct(self):
        def mocked_authenticate(configuration, remote=None):
            if configuration.auth != ("valid_user", "valid_password"):
                raise AuthFailedError()
            else:
                return UserInfo(is_authenticated=True)

        write_default_config(self.f)
        with patch('enstaller.config.authenticate', mocked_authenticate):
            config = Configuration()
            config.set_auth("invalid_user", "invalid_password")

            with self.assertRaises(AuthFailedError):
                usr = config._checked_change_auth(self.f)

            config = Configuration()
            config.set_auth("valid_user", "valid_password")
            usr = config._checked_change_auth(self.f)

            self.assertTrue(usr.is_authenticated)

    @patch('enstaller.config.authenticate', return_value=old_auth_user)
    def test_remote_success(self, mock1):
        write_default_config(self.f)

        config = Configuration()
        config.set_auth("usr", "password")

        usr = config._checked_change_auth(self.f)
        self.assertEqual(usr, DUMMY_USER)

    def test_nones(self):
        config = Configuration()

        with self.assertRaises(InvalidConfiguration):
            config.set_auth(None, None)

    def test_empty_strings(self):
        config = Configuration()
        config.set_auth("", "")

        with self.assertRaises(InvalidConfiguration):
            config._checked_change_auth(self.f)


class TestSubscriptionLevel(unittest.TestCase):
    def test_unsubscribed_user(self):
        user_info = UserInfo(True)
        self.assertEqual(user_info.subscription_level, "Canopy / EPD Free")

        user_info = UserInfo(False)
        self.assertIsNone(user_info.subscription_level)

    def test_subscribed_user(self):
        user_info = UserInfo(True, has_subscription=True)
        self.assertEqual(user_info.subscription_level, "Canopy / EPD Basic or above")

        user_info = UserInfo(True, has_subscription=False)
        self.assertEqual(user_info.subscription_level, "Canopy / EPD Free")

        user_info = UserInfo(False, has_subscription=False)
        self.assertIsNone(user_info.subscription_level)


class TestWebAuth(unittest.TestCase):
    def setUp(self):
        self.config = Configuration()

    def test_invalid_auth_args(self):
        with self.assertRaises(AuthFailedError):
            _web_auth((None, None), self.config.api_url)

    @responses.activate
    def test_simple(self):
        # Given
        responses.add(responses.GET, self.config.api_url, status=200,
                      body=json.dumps(R_JSON_AUTH_RESP))

        self.assertEqual(_web_auth((FAKE_USER, FAKE_PASSWORD),
                                   self.config.api_url),
                         UserInfo.from_json(R_JSON_AUTH_RESP))

    def test_connection_failure(self):
        with patch("enstaller.auth.requests.get",
                   side_effect=requests.exceptions.ConnectionError):
            with self.assertRaises(AuthFailedError):
                _web_auth((FAKE_USER, FAKE_PASSWORD), self.config.api_url)

    @responses.activate
    def test_http_failure(self):
        # Given
        config = Configuration()
        responses.add(responses.GET, config.api_url, body="", status=404,
                      content_type='application/json')

        # When/Then
        with self.assertRaises(AuthFailedError):
            _web_auth((FAKE_USER, FAKE_PASSWORD), self.config.api_url)

    def _no_webservice_config(self):
        config = Configuration()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)
        config.disable_webservice()
        config.set_indexed_repositories(["http://acme.com"])

        return config

    def test_auth_failure_404(self):
        # Given
        config = self._no_webservice_config()
        responses.add(responses.HEAD, config.indices[0][0],
                      body="", status=404,
                      content_type='application/json')

        # When/Given
        with self.assertRaises(AuthFailedError):
            authenticate(config)

    def test_auth_failure_50x(self):
        # Given
        config = self._no_webservice_config()
        responses.add(responses.HEAD, config.indices[0][0],
                      status=503, content_type='application/json')

        # When/Given
        with self.assertRaises(AuthFailedError):
            authenticate(config)

    @responses.activate
    def test_auth_failure_401(self):
        # Given
        config = self._no_webservice_config()
        responses.add(responses.HEAD, config.indices[0][0],
                      body="", status=401,
                      content_type='application/json')

        # When/Given
        with self.assertRaises(AuthFailedError):
            authenticate(config)

    @responses.activate
    def test_unauthenticated_user(self):
        responses.add(responses.GET, self.config.api_url,
                      body=json.dumps(R_JSON_NOAUTH_RESP),
                      content_type='application/json')
        with self.assertRaises(AuthFailedError):
            _web_auth((FAKE_USER, FAKE_PASSWORD), self.config.api_url)


class TestAuthenticate(unittest.TestCase):
    @fake_keyring
    def test_use_webservice_valid_user(self):
        config = Configuration()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)

        with patch("enstaller.auth._web_auth") as mocked_auth:
            authenticate(config)
            self.assertTrue(mocked_auth.called)

    @fake_keyring
    def test_use_webservice_invalid_user(self):
        config = Configuration()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)

        with patch("enstaller.auth._web_auth") as mocked_auth:
            mocked_auth.return_value = UserInfo(False)

            with self.assertRaises(AuthFailedError):
                authenticate(config)

    @fake_keyring
    def test_use_remote(self):
        config = Configuration()
        config.disable_webservice()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)

        user = authenticate(config)
        self.assertEqual(user, UserInfo(True))

    @fake_keyring
    @responses.activate
    def test_non_existing_remote(self):
        repo_url = "http://api.enthought.com/dummy/repo"
        config = Configuration()
        config.disable_webservice()
        config.set_auth(FAKE_USER, FAKE_PASSWORD)
        config.set_indexed_repositories([repo_url])

        responses.add(responses.HEAD, repo_url + "/index.json",
                      body="", status=404,
                      content_type='application/json')
        with self.assertRaises(EnstallerException):
            authenticate(config)


class SearchTestCase(unittest.TestCase):
    pass


class InstallTestCase(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
