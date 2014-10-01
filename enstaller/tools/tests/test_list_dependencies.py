import json
import textwrap

from egginst._compat import TestCase

from enstaller.config import Configuration
from enstaller.plat import custom_plat
from enstaller.session import Session
from enstaller.tests.common import (mock_print, mocked_session_factory,
                                    dummy_repository_package_factory,
                                    R_JSON_AUTH_RESP)
from enstaller.vendor import responses

from enstaller.tools.list_dependencies import query_platform, main


def _mock_index(entries, platform=None):
    platform = platform or custom_plat
    index = dict((entry.key, entry.s3index_data) for entry in entries)

    responses.add(responses.GET,
                  "https://api.enthought.com/eggs/{0}/index.json". \
                          format(platform),
                  body=json.dumps(index), status=200,
                  content_type='application/json')

class TestListDependencies(TestCase):
    @responses.activate
    def test_simple(self):
        # Given
        config = Configuration()
        session = Session.from_configuration(config)
        entries = [
            dummy_repository_package_factory("MKL", "10.3", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 1,
                                             dependencies=["MKL 10.3"]),
        ]
        _mock_index(entries)
        r_output = textwrap.dedent("""\
            Resolving dependencies for numpy: numpy-1.8.0-1.egg
                mkl 10.3
        """)

        # When
        with mock_print() as m:
            query_platform(session, config.indices, "numpy", custom_plat)

        # Then
        self.assertMultiLineEqual(m.value, r_output)

class TestMainListDependencies(TestCase):
    def _mock_auth(self):
        responses.add(responses.GET,
                      "https://api.enthought.com/accounts/user/info/",
                      body=json.dumps(R_JSON_AUTH_RESP), status=200,
                      content_type='application/json')

    @responses.activate
    def test_another_platform(self):
        # Given
        self._mock_auth()
        entries = [
            dummy_repository_package_factory("MKL", "10.3", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 1,
                                             dependencies=["MKL 10.3"]),
        ]
        _mock_index(entries, "rh5-64")
        _mock_index([], "rh5-32")
        r_output = textwrap.dedent("""\
            Resolving dependencies for numpy: numpy-1.8.0-1.egg
                mkl 10.3
        """)

        # When
        with mock_print() as m:
            main(["numpy", "--platform=rh5-32"])

        # Then
        self.assertMultiLineEqual(m.value,
                                  "No egg found for requirement numpy\n")

        # When
        with mock_print() as m:
            main(["numpy", "--platform=rh5-64"])

        # Then
        self.assertMultiLineEqual(m.value, r_output)

    @responses.activate
    def test_simple(self):
        # Given
        self._mock_auth()
        entries = [
            dummy_repository_package_factory("MKL", "10.3", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 1,
                                             dependencies=["MKL 10.3"]),
        ]
        _mock_index(entries)
        r_output = textwrap.dedent("""\
            Resolving dependencies for numpy: numpy-1.8.0-1.egg
                mkl 10.3
        """)

        # When
        with mock_print() as m:
            main(["numpy"])

        # Then
        self.assertMultiLineEqual(m.value, r_output)
