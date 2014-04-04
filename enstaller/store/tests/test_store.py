import json
import os
import shutil
import sys
import tempfile
import unittest
import urlparse
import uuid

from cStringIO import StringIO

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from okonomiyaki.repositories.enpkg import EnpkgS3IndexEntry

from egginst.testing_utils import network
from egginst.tests.common import DUMMY_EGG, DUMMY_WITH_PROXY_EGG

from enstaller.errors import InvalidConfiguration
from enstaller.store.indexed import LocalIndexedStore, RemoteHTTPIndexedStore
from enstaller.store.joined import JoinedStore

DUMMY_URL = "http://example.com"
API_URL = "http://api.enthought.com/eggs/rh5-64"

class TestRemoteHTTPStore(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_simple_query(self):
        dummy_entry = EnpkgS3IndexEntry.from_egg(DUMMY_EGG, "free", True)
        dummy_index = {
            dummy_entry.egg_basename: dummy_entry.to_dict()
        }
        with mock.patch("enstaller.store.indexed.RemoteHTTPIndexedStore.get_index",
                        lambda ignored: dummy_index):
            store = RemoteHTTPIndexedStore(DUMMY_URL, self.d)
            store.connect()
            result = list(store.query(name="dummy"))

            self.assertEqual(len(result), 1)

    @network
    def test_simple_query_connected(self):
        # FIXME: this is a dumb test, but it allows us to check basic network
        # operations for now.
        store = RemoteHTTPIndexedStore(API_URL, self.d)
        store.connect()
        result = list(store.query(name="numpy"))

        self.assertTrue(len(result) > 1)

    def test_get_data_no_auth_in_url(self):
        """
        Check that auth information passed to store.connect is properly
        encoded in request header.
        """
        auth = ("john", "doe")
        r_headers = {"User-agent": "enstaller"}
        r_unredirected_headers = {"Authorization": "Basic {0}". \
                                  format(":".join(auth).encode("base64").strip())}

        store = RemoteHTTPIndexedStore(API_URL, self.d)

        build_opener = mock.Mock()

        def dummy_index_open(request):
            return StringIO("{}")
        build_opener.open = dummy_index_open

        with mock.patch("enstaller.store.indexed.RemoteHTTPIndexedStore.opener",
                        build_opener):
            store.connect(auth)

            def dummy_open(request):
                self.assertEqual(request.headers, r_headers)
                self.assertEqual(request.unredirected_hdrs,
                                 r_unredirected_headers)
            build_opener.open = dummy_open
            store.get_data("")

    def test_get_data_auth_in_url(self):
        """
        Check that auth information in the URL is properly encoded in request
        header.
        """
        auth = ("john", "doe")
        r_headers = {"User-agent": "enstaller"}
        r_unredirected_headers = {"Authorization": "Basic {0}". \
                                  format(":".join(auth).encode("base64").strip())}

        def _inject_user_pass_in_url(url, auth):
            scheme, netloc, path, params, query, fragment = urlparse.urlparse(API_URL)
            netloc = "{user}:{password}@{netloc}".format(user=auth[0],
                                                         password=auth[1],
                                                         netloc=netloc)
            return urlparse.urlunparse((scheme, netloc, path, params, query, fragment))

        url = _inject_user_pass_in_url(API_URL, auth)
        store = RemoteHTTPIndexedStore(url, self.d)

        build_opener = mock.Mock()

        def dummy_index_open(request):
            return StringIO("{}")
        build_opener.open = dummy_index_open

        with mock.patch("enstaller.store.indexed.RemoteHTTPIndexedStore.opener",
                        build_opener):
            store.connect()

            def dummy_open(request):
                self.assertEqual(request.headers, r_headers)
                self.assertEqual(request.unredirected_hdrs,
                                 r_unredirected_headers)
            build_opener.open = dummy_open
            store.get_data("")

    def test_get_data_opener_errors(self):
        store = RemoteHTTPIndexedStore(API_URL, self.d)

        build_opener = mock.Mock()

        def dummy_index_open(request):
            return StringIO("{}")
        build_opener.open = dummy_index_open

        with mock.patch("enstaller.store.indexed.RemoteHTTPIndexedStore.opener",
                        build_opener):
            store.connect()
            import urllib2

            def http_error_open(request):
                raise urllib2.HTTPError(1, 404, 3, 4, StringIO())
            build_opener.open = http_error_open
            with self.assertRaises(KeyError):
                store.get_data("")

            def url_error_open(request):
                raise urllib2.URLError("yeah")
            build_opener.open = url_error_open
            with self.assertRaises(Exception):
                store.get_data("")

class TestLocalIndexedStore(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_simple_query(self):
        dummy_entry = EnpkgS3IndexEntry.from_egg(DUMMY_EGG, "free", True)
        dummy_index = {
            dummy_entry.s3index_key: dummy_entry.s3index_data
        }

        with open(os.path.join(self.d, "index.json"), "w") as fp:
            json.dump(dummy_index, fp)

        store = LocalIndexedStore(self.d)
        store.connect()

        params = {"type": "egg"}
        result = list(store.query(**params))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "dummy-1.0.1-1.egg")

        result = list(store.query_keys(**params))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "dummy-1.0.1-1.egg")

        params = {"type": "fubar"}
        result = list(store.query(**params))
        self.assertEqual(len(result), 0)

        result = list(store.query_keys(**params))
        self.assertEqual(len(result), 0)

    def test_get_data_missing_key(self):
        with open(os.path.join(self.d, "index.json"), "w") as fp:
            json.dump({}, fp)

        store = LocalIndexedStore(self.d)
        store.connect()

        self.assertRaises(KeyError, lambda: store.get_data("dummy_key"))

    def test_invalid_non_existing_root(self):
        store = LocalIndexedStore(self.d)
        with self.assertRaises(InvalidConfiguration):
            store.connect()

def _local_store_factory(entries, basedir):
    d = os.path.join(basedir, str(uuid.uuid4())[:8])
    os.makedirs(d)

    dummy_index = {}
    for egg, entry in entries:
        shutil.copy(egg, d)
        dummy_index[entry.s3index_key] = entry.s3index_data

    with open(os.path.join(d, "index.json"), "w") as fp:
        json.dump(dummy_index, fp)

    return LocalIndexedStore(d)

class TestJoinedStore(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.maxDiff = None

        dummy_entry = EnpkgS3IndexEntry.from_egg(DUMMY_EGG, "free", True)
        dummy_with_proxy_entry = EnpkgS3IndexEntry.from_egg(DUMMY_WITH_PROXY_EGG, "free", True)

        store = self._build_simple_joined_store([(DUMMY_EGG, dummy_entry)],
                                                [(DUMMY_WITH_PROXY_EGG, dummy_with_proxy_entry)])
        store.connect()

        self.dummy_entry = dummy_entry
        self.dummy_with_proxy_entry = dummy_with_proxy_entry
        self.store = store

    def tearDown(self):
        shutil.rmtree(self.d)

    def _build_simple_joined_store(self, repo1_entries, repo2_entries):
        store1 = _local_store_factory(repo1_entries, self.d)

        store2 = _local_store_factory(repo2_entries, self.d)

        store = JoinedStore([store1, store2])

        return store

    def test_simple_query(self):
        r_dummy_metadata = self.dummy_entry.s3index_data

        metadata = self.store.get_metadata("dummy-1.0.1-1.egg")
        metadata.pop("store_location")

        self.assertEqual(metadata, r_dummy_metadata)

    def test_exists(self):
        store = self.store

        self.assertTrue(store.exists(self.dummy_entry.s3index_key))
        self.assertTrue(store.exists(self.dummy_with_proxy_entry.s3index_key))
        self.assertFalse(store.exists("floupiga"))

    def test_non_existing_key(self):
        self.assertRaises(KeyError, lambda: self.store.get_metadata("floupiga"))
        self.assertRaises(KeyError, lambda: self.store.get_data("floupiga"))
        self.assertRaises(KeyError, lambda: self.store.get("floupiga"))

    def test_get_data(self):
        store = self.store
        key = self.dummy_with_proxy_entry.s3index_key

        fp = store.get_data(key)
        try:
            self.assertEqual(os.path.basename(fp.name), os.path.basename(DUMMY_WITH_PROXY_EGG))
        finally:
            fp.close()

    def test_get(self):
        store = self.store
        key = self.dummy_with_proxy_entry.s3index_key
        r_metadata = self.dummy_with_proxy_entry.s3index_data

        fp, metadata = store.get(key)
        try:
            self.assertEqual(os.path.basename(fp.name), os.path.basename(DUMMY_WITH_PROXY_EGG))

            metadata.pop("store_location")
            self.assertEqual(metadata, r_metadata)
        finally:
            fp.close()
