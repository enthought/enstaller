import bz2
import gzip
from hashlib import md5
import json
import os.path
import re
import urllib2
import errno


from cStringIO import StringIO


class CachedHandler(urllib2.BaseHandler):
    cache_re = re.compile('index.*\\.json')

    def __init__(self, cache_dir):
        self._metadata_path = os.path.join(
            cache_dir, 'index_cache', 'metadata.json')
        self._index_path = os.path.join(
            cache_dir, 'index_cache', 'index.json')

    def read_metadata(self):
        try:
            metadata = json.load(open(self._metadata_path, 'rb'))
        except (ValueError, IOError):
            metadata = {}

        return metadata

    def cache_is_valid(self, metadata=None):
        metadata = metadata or self.read_metadata()
        if ('etag' in metadata  # metadata has an etag
            and 'md5' in metadata  # and an md5 sum
            and os.path.exists(self._index_path)  # and the index exists
            ):
            # All the data is there, check if it's valid
            sum = md5()
            for line in open(self._index_path, 'rb'):
                sum.update(line)

            # And if so, add an etag header
            if metadata['md5'] == sum.hexdigest():
                return True
        return False

    def clear_cache(self):
        for path in self._metadata_path, self._index_path:
            try:
                os.remove(self._metadata_path)
            except OSError:
                pass

    def fill_cache(self, etag, content):
        metadata = {
            'etag': etag,
            'md5': md5(content).hexdigest(),
        }
        try:
            os.makedirs(os.path.dirname(self._index_path))
        except OSError as e:
            if e.errno == errno.EEXIST:
                # File exists
                pass
            else:
                raise
        open(self._index_path, 'wb').write(content)
        json.dump(metadata, open(self._metadata_path, 'wb'))

    # BaseHandler API Methods #

    def http_request(self, req):
        metadata = self.read_metadata()

        if self.cache_re.search(req.get_full_url()) and self.cache_is_valid(metadata):
            req.headers['If-None-Match'] = metadata['etag']

        return req

    https_request = http_request

    def http_error_304(self, req, fp, code, msg, headers):
        metadata = self.read_metadata()

        if not self.cache_is_valid(metadata):
            self.clear_cache()
            return self.parent.open(req.get_full_url())

        res = urllib2.addinfourl(open(self._index_path, 'rb'),
                                 headers, req.get_full_url())
        res.code = code
        res.msg = msg
        return res

    def http_response(self, req, response):
        etag = response.headers.get('Etag')
        if etag and response.code == 200 and self.cache_re.search(response.url):
            self.fill_cache(etag, response.read())
            res = urllib2.addinfourl(open(self._index_path, 'rb'),
                                          response.headers, response.url)
            res.code = response.code
            res.msg = response.msg
            return res

        return response

    https_response = http_response


class CompressedHandler(urllib2.BaseHandler):
    compression_types = [
        ('bzip2', bz2.decompress),
        ('gzip', lambda data: gzip.GzipFile(fileobj=StringIO(data)).read()),
        ('*', lambda data: data)
    ]

    def http_request(self, req):
        if not req.headers.get('Accept-Encoding'):
            req.headers['Accept-Encoding'] = ','.join(
                [enc for enc, _ in self.compression_types])
        return req

    https_request = http_request

    def http_response(self, req, response):
        content_encoding = response.headers.get('Content-Encoding')
        if not content_encoding:
            return response

        for encoding, decompress in self.compression_types:
            if encoding in content_encoding:
                decompressed = decompress(response.read())
                response.read = lambda: decompressed

        return response

    https_response = http_response
