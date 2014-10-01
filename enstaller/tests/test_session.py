from egginst._compat import TestCase

from enstaller.config import Configuration
from enstaller.session import Session
from enstaller.tests.common import mocked_session_factory
from enstaller.vendor.cachecontrol.adapter import CacheControlAdapter


class TestSession(TestCase):
    def test_etag(self):
        # Given
        config = Configuration()
        session = mocked_session_factory(config.repository_cache)
        old_adapters = session._session.adapters.copy()

        # When
        with session.etag():
            pass

        # Then
        self.assertFalse(isinstance(session._session.adapters["http://"],
                                    CacheControlAdapter))
        self.assertFalse(isinstance(session._session.adapters["https://"],
                                    CacheControlAdapter))

    def test_from_configuration(self):
        # Given
        config = Configuration()

        # When/Then
        with Session.from_configuration(config) as session:
            self.assertTrue(session._session.verify)

        # When/Then
        with Session.from_configuration(config, verify=False) as session:
            self.assertFalse(session._session.verify)
