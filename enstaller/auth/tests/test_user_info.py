import json

from egginst._compat import TestCase

from enstaller.config import Configuration
from enstaller.session import Session
from enstaller.tests.common import R_JSON_AUTH_RESP
from enstaller.auth.user_info import UserInfo
from enstaller.vendor import responses


class TestUserInfo(TestCase):
    @responses.activate
    def test_simple_legacy_canopy(self):
        # Given
        url = "https://api.enthought.com"

        config = Configuration()
        config.update(store_url=url)

        responses.add(responses.GET, url + "/accounts/user/info/", status=200,
                      body=json.dumps(R_JSON_AUTH_RESP))

        session = Session.from_configuration(config)
        session.authenticate(config.auth)

        # When
        user_info = UserInfo.from_session(session)

        # Then
        self.assertEqual(user_info.first_name, R_JSON_AUTH_RESP["first_name"])

    @responses.activate
    def test_simple_old_legacy(self):
        # Given
        url = "https://acme.com"

        config = Configuration()
        config.update(use_webservice=False)
        config.update(indexed_repositories=[url])

        responses.add(responses.HEAD, config.indices[0][0], status=200)

        session = Session.from_configuration(config)
        session.authenticate(config.auth)

        # When
        user_info = UserInfo.from_session(session)

        # Then
        self.assertTrue(user_info.is_authenticated)

    @responses.activate
    def test_simple_brood_auth(self):
        # Given
        url = "https://acme.com"
        token_url = url + "/api/v0/json/auth/tokens/auth"


        config = Configuration()
        config.update(store_url="brood+" + url)

        responses.add(responses.POST, token_url, status=200,
                      body=json.dumps({"token": "dummy token"}))

        session = Session.from_configuration(config)
        session.authenticate(config.auth)

        # When
        user_info = UserInfo.from_session(session)

        # Then
        self.assertTrue(user_info.is_authenticated)


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
