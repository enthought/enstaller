from egginst._compat import TestCase

import base64
import json
import os.path
import shutil
import tempfile

from mock import patch

import enstaller.config

from enstaller.auth import DUMMY_USER, UserInfo
from enstaller.auth.auth_managers import (LegacyCanopyAuthManager,
                                          OldRepoAuthManager)
from enstaller.config import Configuration, write_default_config
from enstaller.session import Session
from enstaller.errors import (AuthFailedError, EnstallerException,
                              InvalidConfiguration)
from enstaller.tests.common import DummyAuthenticator, fake_keyring
from enstaller.vendor import requests, responses


basic_user = UserInfo(True, first_name="Jane", last_name="Doe", has_subscription=True)
free_user = UserInfo(True, first_name="John", last_name="Smith", has_subscription=False)
anon_user = UserInfo(False)
old_auth_user = DUMMY_USER

def compute_creds(username, password):
    s = "{0}:{1}".format(username, password)
    return base64.b64encode(s.encode("ascii")).rstrip()

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
class CheckedChangeAuthTestCase(TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, "enstaller4rc")
        self.session = Session(DummyAuthenticator(), self.d)

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_no_acct(self):
        def mocked_authenticate(auth):
            if auth != ("valid_user", "valid_password"):
                raise AuthFailedError()

        write_default_config(self.f)
        with patch.object(self.session, 'authenticate', mocked_authenticate):
            config = Configuration()
            auth = ("invalid_user", "invalid_password")

            with self.assertRaises(AuthFailedError):
                usr = config._checked_change_auth(auth, self.session, self.f)

            config = Configuration()
            auth = ("valid_user", "valid_password")
            usr = config._checked_change_auth(auth, self.session, self.f)

            self.assertTrue(usr.is_authenticated)
            self.assertEqual(config.auth, ("valid_user", "valid_password"))

    def test_remote_success(self):
        write_default_config(self.f)

        config = Configuration()
        auth = ("usr", "password")
        session = Session(DummyAuthenticator(old_auth_user), self.d)

        usr = config._checked_change_auth(auth, session, self.f)
        self.assertEqual(usr, DUMMY_USER)

    def test_nones(self):
        config = Configuration()

        with self.assertRaises(InvalidConfiguration):
            config.set_auth(None, None)


class TestSubscriptionLevel(TestCase):
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


class TestOldReposAuthManager(TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

        self.config = Configuration()
        self.config.disable_webservice()
        self.config.set_indexed_repositories(["http://acme.com"])
        self.session = Session(OldRepoAuthManager(self.config.indices),
                               self.prefix)

    def tearDown(self):
        shutil.rmtree(self.prefix)

    @responses.activate
    def test_simple(self):
        # Given
        responses.add(responses.HEAD, self.config.indices[0][0], status=200,
                      body=json.dumps(R_JSON_AUTH_RESP))

        # When
        self.session.authenticate((FAKE_USER, FAKE_PASSWORD))

        # Then
        self.assertEqual(self.session.user_info, UserInfo(True))

    def test_connection_failure(self):
        with patch.object(self.session._session, "head",
                          side_effect=requests.exceptions.ConnectionError):
            with self.assertRaises(AuthFailedError):
                self.session.authenticate((FAKE_USER, FAKE_PASSWORD))

    @responses.activate
    def test_auth_failure_404(self):
        # Given
        auth = ("nono", "le petit robot")
        responses.add(responses.HEAD, self.config.indices[0][0],
                      body="", status=404,
                      content_type='application/json')

        # When/Given
        with self.assertRaises(AuthFailedError):
            self.session.authenticate(auth)

    @responses.activate
    def test_auth_failure_50x(self):
        # Given
        auth = ("nono", "le petit robot")
        responses.add(responses.HEAD, self.config.indices[0][0],
                      status=503, content_type='application/json')

        # When/Given
        with self.assertRaises(AuthFailedError):
            self.session.authenticate(auth)

    @responses.activate
    def test_auth_failure_401(self):
        # Given
        auth = ("nono", "le petit robot")
        responses.add(responses.HEAD, self.config.indices[0][0],
                      body="", status=401,
                      content_type='application/json')

        # When/Given
        with self.assertRaises(AuthFailedError):
            self.session.authenticate(auth)


class TestLegacyCanopyAuthManager(TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

        self.config = Configuration()
        self.session = Session(LegacyCanopyAuthManager(self.config.api_url),
                               self.prefix)

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_invalid_auth_args(self):
        with self.assertRaises(AuthFailedError):
            self.session.authenticate((None, None))

    @responses.activate
    def test_simple(self):
        # Given
        responses.add(responses.GET, self.config.api_url, status=200,
                      body=json.dumps(R_JSON_AUTH_RESP))

        # When
        self.session.authenticate((FAKE_USER, FAKE_PASSWORD))

        # Then
        self.assertEqual(self.session.user_info,
                         UserInfo.from_json(R_JSON_AUTH_RESP))

    def test_connection_failure(self):
        with patch.object(self.session._session, "get",
                          side_effect=requests.exceptions.ConnectionError):
            with self.assertRaises(AuthFailedError):
                self.session.authenticate((FAKE_USER, FAKE_PASSWORD))

    @responses.activate
    def test_http_failure(self):
        # Given
        config = Configuration()
        responses.add(responses.GET, config.api_url, body="", status=404,
                      content_type='application/json')

        # When/Then
        with self.assertRaises(AuthFailedError):
            self.session.authenticate((FAKE_USER, FAKE_PASSWORD))

    @responses.activate
    def test_unauthenticated_user(self):
        # Given
        responses.add(responses.GET, self.config.api_url,
                      body=json.dumps(R_JSON_NOAUTH_RESP),
                      content_type='application/json')

        # When/Then
        with self.assertRaises(AuthFailedError):
            self.session.authenticate((FAKE_USER, FAKE_PASSWORD))


class TestAuthenticate(TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    @fake_keyring
    @responses.activate
    def test_use_webservice_invalid_user(self):
        # Given
        config = Configuration()
        session = Session(LegacyCanopyAuthManager(config.api_url), self.prefix)
        responses.add(responses.GET, config.api_url,
                      body=json.dumps(R_JSON_NOAUTH_RESP),
                      content_type='application/json')

        # When/Then
        with self.assertRaises(AuthFailedError):
            session.authenticate((FAKE_USER, FAKE_PASSWORD))


class SearchTestCase(TestCase):
    pass


class InstallTestCase(TestCase):
    pass
