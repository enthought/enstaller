"""
A few utilities for python requests.
"""
import base64
import logging
import os
import sqlite3

from io import FileIO

from egginst.vendor.six.moves import urllib
from egginst._compat import buffer

from enstaller.utils import uri_to_path
from enstaller.vendor import requests, sqlite_cache
from enstaller.vendor.cachecontrol.cache import BaseCache
from enstaller.vendor.cachecontrol.controller import CacheController


logger = logging.getLogger(__name__)


class FileResponse(FileIO):
    """
    A FileIO subclass that can be used as an argument to
    HTTPAdapter.build_response method from the requests library.
    """
    def __init__(self, name, mode, closefd=True):
        super(FileResponse, self).__init__(name, mode, closefd)

        self.status = 200
        self.headers = {}
        self.reason = None

    def get_all(self, name, default):
        result = self.headers.get(name)
        if not result:
            return default
        return [result]

    def getheaders(self, name):
        return self.get_all(name, [])

    def release_conn(self):
        self.close()


class LocalFileAdapter(requests.adapters.HTTPAdapter):
    """
    A requests adapter to support local file IO.

    Example
    -------

    session = requests.session()
    session.mount("file://", LocalFileAdapter())

    session.get("file:///bin/ls")
    """
    def build_response_from_file(self, request, stream):
        path = uri_to_path(request.url)
        stat_info = os.stat(path)

        response = self.build_response(request, FileResponse(path, "rb"))
        response.headers["content-length"] = str(stat_info.st_size)
        return response

    def send(self, request, stream=False, timeout=None,
             verify=True, cert=None, proxies=None):

        return self.build_response_from_file(request, stream)


class _ResponseIterator(object):
    """
    A simple iterator on top of a requests response

    It supports the `len` protocol so that packages such as click can show an
    ETA when fetching by chunk.

    Example
    -------
    >>> resp = requests.get("http://acme.com", stream=True)
    >>> for chunk in _ResponseIterator(resp):
        print len(chunk)
    """
    def __init__(self, response):
        self._response = response
        self._size = int(self._response.headers.get("content-length", 0))
        self._chunk_size = 1024

    def __iter__(self):
        self._iter = self._response.iter_content(self._chunk_size)
        return self

    def __next__(self):
        return next(self._iter)

    next = __next__

    def __len__(self):
        return int(self._size / self._chunk_size + 1)


class _NullCache(object):
    def close(self):
        pass

    def get(self, key):
        return None

    def set(self, key, value):
        pass

    def delete(self, key):
        pass


class DBCache(BaseCache):
    """
    A Sqlite-backed cache.

    Using sqlite guarantees data consistency without much overhead and
    without the need of usually brittle file locks, or external services
    (impractical in many cases)
    """
    def __init__(self, uri=":memory:", capacity=10):
        try:
            self._cache = sqlite_cache.SQLiteCache(uri, capacity,
                                                   use_separate_connection=True)
        except sqlite3.Error as e:
            logger.warn("Could not create sqlite cache: %r", e)
            self._cache = _NullCache()
        self.closed = False

    def close(self):
        if not self.closed:
            self._cache.close()
            self.closed = True

    def _encode_key(self, key):
        return base64.b64encode(key.encode("utf8")).decode("utf8")

    def _encode_value(self, value):
        data = base64.b64encode(value)
        return buffer(data)

    def _decode_value(self, encoded_value):
        return base64.b64decode(bytes(encoded_value))

    def get(self, key):
        try:
            encoded_value = self._cache.get(self._encode_key(key))
        except sqlite3.Error as e:
            logger.warn("Could not fetch data from cache: %r", e)
            return None
        else:
            if encoded_value is not None:
                try:
                    return self._decode_value(encoded_value)
                except UnicodeDecodeError as e:
                    msg = "Could not fetch data from cache: (decoding error)"
                    logger.warn(msg)
                    return None
                except Exception as e:
                    msg = "Could not fetch data from cache: {0!r}".format(e)
                    logger.warn(msg)
                    return None
            else:
                return None

    def set(self, key, value):
        try:
            self._cache.set(self._encode_key(key), self._encode_value(value))
        except sqlite3.Error as e:
            logger.warn("Could not fetch data from cache: %r", e)

    def delete(self, key):
        try:
            self._cache.delete(self._encode_key(key))
        except sqlite3.Error as e:
            logger.warn("Could not fetch data from cache: %r", e)


class QueryPathOnlyCacheController(CacheController):
    """
    A cache controller that caches entries based solely on scheme, hostname and
    path.
    """
    def cache_url(self, uri):
        url = super(QueryPathOnlyCacheController, self).cache_url(uri)
        p = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse((p.scheme, p.hostname, p.path, "", "", ""))
