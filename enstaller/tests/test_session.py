from egginst._compat import TestCase

from enstaller.config import Configuration
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
