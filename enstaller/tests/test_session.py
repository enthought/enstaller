import json
import mock
import os
import shutil
import tempfile

import enstaller

from egginst.vendor.six.moves import unittest

from enstaller.auth.auth_managers import (BroodAuthenticator,
                                          LegacyCanopyAuthManager,
                                          OldRepoAuthManager)
from enstaller.config import Configuration
from enstaller.errors import EnstallerException
from enstaller.session import _PatchedRawSession, Session
from enstaller.tests.common import R_JSON_AUTH_RESP, mocked_session_factory
from enstaller.vendor import responses
from enstaller.vendor.cachecontrol.adapter import CacheControlAdapter
from enstaller.vendor.requests.adapters import HTTPAdapter


class Test_PatchedRawSession(unittest.TestCase):
    def test_mount_simple(self):
        # Given
        session = _PatchedRawSession()
        fake_adapter = mock.Mock()

        # When
        session.mount("http://", fake_adapter)

        # Then
        self.assertIs(session.adapters["http://"], fake_adapter)
        self.assertIsNot(session.adapters["https://"], fake_adapter)

    def test_umount_simple(self):
        # Given
        session = _PatchedRawSession()
        old_adapters = session.adapters.copy()
        fake_adapter = mock.Mock()

        # When
        session.mount("http://", fake_adapter)
        adapter = session.umount("http://")

        # Then
        self.assertIs(adapter, fake_adapter)
        self.assertIsNot(session.adapters["http://"], fake_adapter)
        self.assertIs(session.adapters["http://"], old_adapters["http://"])

    def test_nested_umount(self):
        # Given
        session = _PatchedRawSession()
        old_adapters = session.adapters.copy()
        fake_adapter1 = mock.Mock()
        fake_adapter2 = mock.Mock()

        # When
        session.mount("http://", fake_adapter1)
        session.mount("http://", fake_adapter2)

        # Then
        self.assertIs(session.adapters["http://"], fake_adapter2)

        # When
        adapter = session.umount("http://")

        # Then
        self.assertIs(session.adapters["http://"], fake_adapter1)
        self.assertIs(adapter, fake_adapter2)

        # When
        adapter = session.umount("http://")

        # Then
        self.assertIs(adapter, fake_adapter1)
        self.assertIs(session.adapters["http://"], old_adapters["http://"])


class TestSession(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_etag(self):
        # Given
        config = Configuration()
        session = mocked_session_factory(config.repository_cache)

        # When
        with session.etag():
            pass

        # Then
        self.assertFalse(isinstance(session._raw.adapters["http://"],
                                    CacheControlAdapter))
        self.assertFalse(isinstance(session._raw.adapters["https://"],
                                    CacheControlAdapter))

    def _assert_use_etag_cache_controller(self, session):
        for prefix in ("http://", "https://"):
            self.assertTrue(isinstance(session._raw.adapters[prefix],
                                       CacheControlAdapter))

    def _assert_use_default_adapter(self, session):
        for prefix in ("http://", "https://"):
            self.assertTrue(isinstance(session._raw.adapters[prefix],
                                       HTTPAdapter))

    def test_nested_etag(self):
        # Given
        session = mocked_session_factory(self.prefix)

        # When/Then
        with session.etag():
            self._assert_use_etag_cache_controller(session)
            with session.etag():
                self._assert_use_etag_cache_controller(session)
            self._assert_use_etag_cache_controller(session)

            with session.etag():
                self._assert_use_etag_cache_controller(session)
                with session.etag():
                    self._assert_use_etag_cache_controller(session)
                self._assert_use_etag_cache_controller(session)
        self._assert_use_default_adapter(session)

    def test_multiple_etag(self):
        # Given
        config = Configuration()
        session = mocked_session_factory(config.repository_cache)

        # When
        with mock.patch("enstaller.session.CacheControlAdapter") as m:
            with session.etag():
                pass
            with session.etag():
                pass

        # Then
        self.assertFalse(isinstance(session._raw.adapters["http://"],
                                    CacheControlAdapter))
        self.assertFalse(isinstance(session._raw.adapters["https://"],
                                    CacheControlAdapter))
        self.assertEqual(m.call_count, 4)

    def test_max_retries(self):
        # Given
        config = Configuration()

        # When/Then
        with Session.from_configuration(config) as session:
            for prefix in ("http://", "https://"):
                self.assertEqual(session._raw.adapters[prefix].max_retries, 0)

        # When/Then
        config.update(max_retries=3)
        with Session.from_configuration(config) as session:
            for prefix in ("http://", "https://"):
                self.assertEqual(session._raw.adapters[prefix].max_retries, 3)

    def test_max_retries_with_etag(self):
        # Given
        config = Configuration()

        # When/Then
        with Session.from_configuration(config) as session:
            with session.etag():
                for prefix in ("http://", "https://"):
                    self.assertEqual(session._raw.adapters[prefix].max_retries, 0)

        # When/Then
        config.update(max_retries=3)
        with Session.from_configuration(config) as session:
            with session.etag():
                for prefix in ("http://", "https://"):
                    self.assertEqual(session._raw.adapters[prefix].max_retries, 3)

    def test_from_configuration(self):
        # Given
        config = Configuration()

        # When/Then
        with Session.from_configuration(config) as session:
            self.assertTrue(session._raw.verify)
            self.assertIsInstance(session._authenticator, LegacyCanopyAuthManager)

        # When/Then
        config = Configuration()
        config.update(verify_ssl=False)
        with Session.from_configuration(config) as session:
            self.assertFalse(session._raw.verify)

        # Given
        config = Configuration()
        config.update(verify_ssl=False, use_webservice=False)

        # When/Then
        with Session.from_configuration(config) as session:
            self.assertFalse(session._raw.verify)
            self.assertIsInstance(session._authenticator, OldRepoAuthManager)

        # Given
        config = Configuration()
        config.update(store_url="brood+http://acme.com")

        # When/Then
        with Session.from_configuration(config) as session:
            self.assertIsInstance(session._authenticator, BroodAuthenticator)

    @responses.activate
    def test_authenticated_from_configuration(self):
        # Given
        url = "http://acme.com"
        responses.add(responses.GET, url)
        responses.add(responses.GET, url + "/accounts/user/info/",
                      body=json.dumps(R_JSON_AUTH_RESP))

        config = Configuration()
        config.update(store_url=url, auth=("yoyo", "yeye"))

        # When
        with Session.authenticated_from_configuration(config) as session:
            resp = session._raw_get(url)

        # Then
        self.assertTrue(resp.status_code, 200)

    @responses.activate
    def test_authenticated_from_configuration_wo_auth(self):
        # Given
        url = "http://acme.com"
        responses.add(responses.GET, url)
        responses.add(responses.GET, url + "/accounts/user/info/",
                      body=json.dumps(R_JSON_AUTH_RESP))

        config = Configuration()
        config.update(store_url=url)

        # When/Then
        with self.assertRaises(EnstallerException):
            with Session.authenticated_from_configuration(config):
                pass

    @responses.activate
    def test_agent(self):
        # Given
        url = "http://acme.com"
        responses.add(responses.GET, url)
        config = Configuration()
        r_user_agent = "enstaller/{0}".format(enstaller.__version__)

        # When/Then
        with Session.from_configuration(config) as session:
            resp = session._raw_get(url)
            self.assertTrue(resp.request.headers["user-agent"].
                            startswith(r_user_agent))

    @responses.activate
    def test_download(self):
        # Given
        url = "http://acme.com/foo.bin"
        responses.add(responses.GET, url, body=b"some data")

        config = Configuration()

        # When
        with Session.from_configuration(config) as session:
            target = session.download(url)

        # Then
        try:
            self.assertTrue(os.path.exists(target))
            with open(target, "rb") as fp:
                self.assertEqual(fp.read(), b"some data")
        finally:
            os.unlink(target)

        self.assertEqual(target, "foo.bin")

        # When
        with Session.from_configuration(config) as session:
            target = session.download(url, "foo.baz")

        # Then
        try:
            self.assertTrue(os.path.exists(target))
            with open(target, "rb") as fp:
                self.assertEqual(fp.read(), b"some data")
        finally:
            os.unlink(target)

        self.assertEqual(target, "foo.baz")
