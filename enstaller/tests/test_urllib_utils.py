from cStringIO import StringIO
import hashlib
import json
import os
import os.path
import tempfile
import urllib2
from unittest import TestCase

from enstaller.urllib_utils import CachedHandler


class CacheTest(TestCase):
    def setUp(self):
        self.cache_dir = tempfile.mkdtemp()
        self.metadata_path = os.path.join(self.cache_dir, 'index_cache',
                                          'metadata.json')
        self.index_path = os.path.join(self.cache_dir, 'index_cache',
                                       'index.json')
        self.cache_handler = CachedHandler(self.cache_dir)

    def tearDown(self):
        for filename in os.listdir(self.cache_dir):
            try: os.remove(filename)
            except: pass
        try: os.rmdir(self.cache_dir)
        except: pass

    def _write_cache(self, data, metadata=None):
        os.mkdir(os.path.join(self.cache_dir, 'index_cache'))
        if data:
            open(self.index_path, 'wb').write(data)
        metadata = metadata or {'etag': 'test-etag',
                                'md5': hashlib.md5(data).hexdigest()}
        json.dump(metadata, open(self.metadata_path, 'wb'))

    def test_valid_cache(self):
        self._write_cache('foobly')
        self.assertTrue(self.cache_handler.cache_is_valid())

    def test_invalid_metadata(self):
        self._write_cache('foobly', {'etag': 'whatever', 'md5': 'notright'})
        self.assertFalse(self.cache_handler.cache_is_valid())

    def test_request_valid_cache(self):
        self._write_cache('foobly')
        req = urllib2.Request('http://whatever.com/index.json')
        req = self.cache_handler.http_request(req)
        self.assertEquals(req.headers['If-None-Match'], 'test-etag')

    def test_request_invalid_cache(self):
        """ No If-None-Match header should be added if there is no cached index.
        """
        self._write_cache(None, {'etag': 'whatever', 'md5': 'nomatter'})
        req = urllib2.Request('http://whatever.com/index.json')
        req = self.cache_handler.http_request(req)
        self.assertEquals(req.headers.get('If-None-Match'), None)

    def test_request_no_cache(self):
        req = urllib2.Request('http://whatever.com/index.json')
        req = self.cache_handler.http_request(req)
        self.assertEquals(req.headers.get('If-None-Match'), None)

    def test_write_cache(self):
        req = urllib2.Request('http://foo.com/index.json')
        res = urllib2.addinfourl(StringIO('hello'), {'Etag': 'returned-etag'}, 'http://redirected.com/index-foo.json')
        res.code = 200
        res.msg = 'OK'
        self.cache_handler.http_response(req, res)
        self.assertTrue(os.path.exists(self.index_path))
        self.assertTrue(os.path.exists(self.metadata_path))
        metadata = json.load(open(self.metadata_path, 'rb'))
        self.assertEqual(metadata['etag'], 'returned-etag')
        self.assertEqual(hashlib.md5(open(self.index_path, 'rb').read()).hexdigest(), metadata['md5'])

    def test_valid_304(self):
        self._write_cache('hello again')
        req = urllib2.Request('http://foo.com/index.json')
        res = self.cache_handler.http_error_304(req, StringIO(''), '304', 'Not Modified', {'Etag': 'test-etag'})
        self.assertEqual(res.read(), 'hello again')
        self.assertEqual(res.headers['Etag'], 'test-etag')

    def test_no_etag(self):
        """ No Etag header == no cache written """
        req = urllib2.Request('http://foo.com/index.json')
        res = urllib2.addinfourl(StringIO('foo'), {}, 'http://foo.com/index.json')
        self.cache_handler.http_response(req, res)
        self.assertFalse(os.path.exists(self.metadata_path))
        self.assertFalse(os.path.exists(self.index_path))

    def test_ignore_non_index_etag(self):
        """ Etags are ignored for non-index requests """
        req = urllib2.Request('http://foo.com/')
        res = urllib2.addinfourl(StringIO('foo'), {'Etag': 'whatevs'}, 'http://foo.com/')
        self.cache_handler.http_response(req, res)
        self.assertFalse(os.path.exists(self.metadata_path))
        self.assertFalse(os.path.exists(self.index_path))

    def test_no_write_cache_on_304(self):
        """ Only write cache on 200 responses """
        req = urllib2.Request('http://foo.com/index.json')
        res = urllib2.addinfourl(StringIO('foo'), {'Etag': 'whatevs'}, 'http://foo.com/index.json')
        res.code = 304
        res.msg = 'Not Modified'
        self.cache_handler.http_response(req, res)
        self.assertFalse(os.path.exists(self.metadata_path))
        self.assertFalse(os.path.exists(self.index_path))

