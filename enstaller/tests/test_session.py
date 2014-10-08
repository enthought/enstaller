import mock

import enstaller

from egginst._compat import TestCase

from enstaller.config import Configuration
from enstaller.session import _PatchedRawSession, Session
from enstaller.tests.common import mocked_session_factory
from enstaller.vendor import responses
from enstaller.vendor.cachecontrol.adapter import CacheControlAdapter


class Test_PatchedRawSession(TestCase):
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


class TestSession(TestCase):
    def test_etag(self):
        # Given
        config = Configuration()
        session = mocked_session_factory(config.repository_cache)
        old_adapters = session._raw.adapters.copy()

        # When
        with session.etag():
            pass

        # Then
        self.assertFalse(isinstance(session._raw.adapters["http://"],
                                    CacheControlAdapter))
        self.assertFalse(isinstance(session._raw.adapters["https://"],
                                    CacheControlAdapter))

    def test_nested_etag(self):
        # Given
        config = Configuration()
        session = mocked_session_factory(config.repository_cache)
        old_adapters = session._raw.adapters.copy()

        # When
        with mock.patch("enstaller.session.CacheControlAdapter") as m:
            with session.etag():
                with session.etag():
                    pass

        # Then
        self.assertFalse(isinstance(session._raw.adapters["http://"],
                                    CacheControlAdapter))
        self.assertFalse(isinstance(session._raw.adapters["https://"],
                                    CacheControlAdapter))
        self.assertEqual(m.call_count, 1)

    def test_multiple_etag(self):
        # Given
        config = Configuration()
        session = mocked_session_factory(config.repository_cache)
        old_adapters = session._raw.adapters.copy()

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
        self.assertEqual(m.call_count, 2)

    def test_from_configuration(self):
        # Given
        config = Configuration()

        # When/Then
        with Session.from_configuration(config) as session:
            self.assertTrue(session._raw.verify)

        # When/Then
        with Session.from_configuration(config, verify=False) as session:
            self.assertFalse(session._raw.verify)

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
            self.assertTrue(resp.request.headers["user-agent"]. \
                            startswith(r_user_agent))
