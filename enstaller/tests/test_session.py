import enstaller

from egginst._compat import TestCase

from enstaller.config import Configuration
from enstaller.session import Session
from enstaller.tests.common import mocked_session_factory
from enstaller.vendor import responses
from enstaller.vendor.cachecontrol.adapter import CacheControlAdapter


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
