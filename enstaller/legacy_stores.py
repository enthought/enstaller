import contextlib
import json
import urllib2
import urlparse

from enstaller.errors import InvalidConfiguration
from enstaller.repository import RepositoryPackageMetadata
from enstaller.store.cached import CachedHandler
from enstaller.store.compressed import CompressedHandler
from enstaller.store.indexed import _INDEX_NAME
from enstaller.utils import PY_VER


class URLFetcher(object):
    def __init__(self, cache_dir, auth=None):
        self._auth = auth
        self.cache_dir= cache_dir

    @property
    def _opener(self):
        """ Create custom urlopener with Compression and Caching handlers. """
        # Use handlers from urllib2's default opener, since we already
        # added our proxy handler to it.
        opener = urllib2._opener
        http_handlers = [urllib2.HTTPHandler, urllib2.HTTPSHandler]
        handlers = opener.handlers if opener is not None else http_handlers

        # Add our handlers to the default handlers.
        handlers_ = [CompressedHandler, CachedHandler(self.cache_dir)] + handlers

        return urllib2.build_opener(*handlers_)

    def open(self, url):
        request = urllib2.Request(url)
        if self._auth is not None:
            encoded_auth = "{0}:{1}".format(*self._auth).encode("base64").strip()
            request.add_unredirected_header("Authorization", "Basic " +
                                            encoded_auth)
        request.add_header('User-Agent', 'enstaller')
        return self._opener.open(request)


def _parse_index(json_dict, store_location):
    for key, info in json_dict.items():
        info.setdefault('type', 'egg')
        info.setdefault('python', PY_VER)
        info.setdefault('packages', [])
        info["store_location"] = store_location
        yield RepositoryPackageMetadata.from_json_dict(key, info)


def _webservice_index_parser(webservice_entry_point, fetcher, use_pypi):
    url = webservice_entry_point + _INDEX_NAME
    if use_pypi:
        url +=  "?pypi=true"
    else:
        url +=  "?pypi=false"

    store_location = webservice_entry_point

    fp = fetcher.open(url)
    try:
        json_dict = json.load(fp)
    finally:
        fp.close()

    return _parse_index(json_dict, store_location)


def _old_legacy_index_parser(repository_urls, fetcher):
    for url in repository_urls:
        index = url +  _INDEX_NAME
        p = urlparse.urlparse(index)
        scheme = p.scheme
        if scheme in ("http", "https"):
            fp = fetcher.open(index)
            try:
                json_dict = json.load(fp)
            finally:
                fp.close()
        elif scheme in ("file",):
            with open(p.path, "rb") as fp:
                json_dict = json.load(fp)
        else:
            raise InvalidConfiguration("Unsupported uri: {0!r}".format(url))

        for package in _parse_index(json_dict, url):
            yield package


def legacy_index_parser(config):
    """
    Yield RepositoryPackageMetadata instances from the configured stores.
    """
    fetcher = URLFetcher(config.repository_cache, config.get_auth())
    if config.use_webservice:
        return _webservice_index_parser(config.webservice_entry_point, fetcher,
                                        config.use_pypi)
    else:
        return _old_legacy_index_parser(config.IndexedRepos, fetcher)
