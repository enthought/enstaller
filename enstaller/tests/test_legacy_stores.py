import contextlib
import json
import os.path
import shutil
import sys
import tempfile

from cStringIO import StringIO

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from egginst.testing_utils import network
from egginst.tests.common import mkdtemp

from enstaller.config import Configuration
from enstaller.legacy_stores import URLFetcher
from enstaller.legacy_stores import _old_legacy_index_parser, _webservice_index_parser

from enstaller.tests.common import dummy_repository_package_factory


def package_metadata_iterator(store_location):
    entries = [
        dummy_repository_package_factory("numpy", "1.8.0", 1,
                                         store_location=store_location),
        dummy_repository_package_factory("scipy", "0.14.0", 1,
                                         store_location=store_location)
    ]
    data = StringIO(json.dumps(dict((entry.key, entry.s3index_data) for entry in entries)))
    return contextlib.closing(data)


@contextlib.contextmanager
def mock_urlfetcher():
    return_value = package_metadata_iterator("")
    with mock.patch.object(URLFetcher, "open", return_value=return_value) as m:
        yield m


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
            with fetcher.open(url) as fp:
                json_data = json.load(fp)

        # Then
        self.assertEqual(json_data, r_user_info)

    def test_simple_webservice(self):
        # Given
        config = Configuration()
        config.use_webservice = True
        config.use_pypi = False

        # When
        with mock_urlfetcher():
            fetcher = URLFetcher(config.local, config.get_auth())
            packages = list(
                _webservice_index_parser(config.webservice_entry_point,
                                         fetcher, config.use_pypi))

        # Then
        self.assertTrue(len(packages) > 0)

    def test_simple_no_webservice_https(self):
        # Given
        config = Configuration()
        urls = [
            'https://www.enthought.com/repo/epd/eggs/{SUBDIR}/',
        ]

        # When
        with mock_urlfetcher():
            fetcher = URLFetcher(config.local, config.get_auth())
            packages = list(_old_legacy_index_parser(urls, fetcher))

        # Then
        self.assertTrue(len(packages) > 0)

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
        urls = ["file://{0}/".format(self.tempdir)]

        # When
        with mock_urlfetcher():
            fetcher = URLFetcher(config.local, config.get_auth())
            packages = list(_old_legacy_index_parser(urls, fetcher))

        # Then
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].key, "zope.testing-3.8.3-1.egg")
