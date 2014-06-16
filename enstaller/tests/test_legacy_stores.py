import json
import os.path
import shutil
import sys
import tempfile

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from egginst.testing_utils import network
from egginst.tests.common import mkdtemp

from enstaller.compat import path_to_uri
from enstaller.config import Configuration
from enstaller.fetch import URLFetcher
from enstaller.legacy_stores import legacy_index_parser
from enstaller.plat import custom_plat

from enstaller.tests.common import dummy_repository_package_factory
from enstaller.vendor import responses


def _index_provider(store_location):
    entries = [
        dummy_repository_package_factory("numpy", "1.8.0", 1,
                                         store_location=store_location),
        dummy_repository_package_factory("scipy", "0.14.0", 1,
                                         store_location=store_location)
    ]
    return json.dumps(dict((entry.key, entry.s3index_data) for entry in entries))


class TestLegacyStores(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    @network
    def test_url_fetcher(self):
        # Given
        url = "https://api.enthought.com/accounts/user/info"
        r_user_info = {
            'first_name': None,
            'has_subscription': False,
            'is_active': False,
            'is_authenticated': False,
            'last_name': None,
            'subscription_level': u'unregistered'
        }

        # When
        with mkdtemp() as tempdir:
            fetcher = URLFetcher(tempdir)
            json_data = fetcher.fetch(url).json()

        # Then
        self.assertEqual(json_data, r_user_info)

    @responses.activate
    def test_simple_webservice(self):
        # Given
        config = Configuration()
        config.enable_webservice()
        config.disable_pypi()

        responses.add(responses.GET,
                      "https://api.enthought.com/eggs/{0}/index.json".format(custom_plat),
                      body=_index_provider(""), status=200,
                      content_type='application/json')

        fetcher = URLFetcher(config.repository_cache, config.auth)
        packages = list(legacy_index_parser(fetcher, config.indices))

        # Then
        self.assertTrue(len(packages) > 0)
        self.assertItemsEqual([p.name for p in packages], ["numpy", "scipy"])
        self.assertItemsEqual([p.full_version for p in packages], ["1.8.0-1",
                                                                   "0.14.0-1"])

    @responses.activate
    def test_simple_no_webservice_https(self):
        # Given
        config = Configuration()
        config.set_indexed_repositories([
            'https://www.enthought.com/repo/epd/eggs/{SUBDIR}/',
        ])
        config.disable_webservice()

        responses.add(responses.GET,
                      config.indices[0][0],
                      body=_index_provider(""), status=200,
                      content_type='application/json')

        # When
        fetcher = URLFetcher(config.repository_cache, config.auth)
        packages = list(legacy_index_parser(fetcher, config.indices))

        # Then
        self.assertTrue(len(packages) > 0)
        self.assertItemsEqual([p.name for p in packages], ["numpy", "scipy"])
        self.assertItemsEqual([p.full_version for p in packages], ["1.8.0-1",
                                                                   "0.14.0-1"])


    def test_simple_no_webservice_file(self):
        # Given
        fake_index = {
           "zope.testing-3.8.3-1.egg": {
               "available": True,
               "build": 1,
               "md5": "6041fd75b7fe9187ccef0d40332c6c16",
               "mtime": 1262725254.0,
               "name": "zope.testing",
               "product": "commercial",
               "python": "2.6",
               "size": 514439,
               "type": "egg",
               "version": "3.8.3",
           }
        }
        index_path = os.path.join(self.tempdir, "index.json")
        with open(index_path, "w") as fp:
            fp.write(json.dumps(fake_index))

        config = Configuration()
        config.set_indexed_repositories(["{0}/".format(path_to_uri(self.tempdir))])
        config.disable_webservice()

        # When
        fetcher = URLFetcher(config.repository_cache, config.auth)
        packages = list(legacy_index_parser(fetcher, config.indices))

        # Then
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].key, "zope.testing-3.8.3-1.egg")
