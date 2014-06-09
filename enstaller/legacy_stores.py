import sys
import urllib

import requests

from enstaller.auth import _INDEX_NAME
from enstaller.repository import RepositoryPackageMetadata
from enstaller.requests_utils import LocalFileAdapter
from enstaller.utils import PY_VER


class URLFetcher(object):
    def __init__(self, cache_dir, auth=None):
        self._auth = auth
        self.cache_dir= cache_dir

        session = requests.Session()
        session.mount("file://", LocalFileAdapter())

        self._session = session

    def fetch(self, url):
        return self._session.get(url, stream=True, auth=self._auth)


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

    resp = fetcher.fetch(url)
    resp.raise_for_status()

    return _parse_index(resp.json(), store_location)

def _file_uri_parse_to_path(p):
    """Convert a urlparse.urlparse returns value to a 'normal' path usable in
    open, etc...

    Example
    -------
    >>> from urlparse import urlparse
    >>> _file_uri_parse_to_path(urlparse("file:///c:/server.log"))
    "c:/server.log"
    """
    path = p.path
    if sys.platform == "win32" and p.path.startswith("/"):
        path = path[1:]
    return urllib.url2pathname(path)

def _old_legacy_index_parser(repository_urls, fetcher):
    for url in repository_urls:
        index = url +  _INDEX_NAME
        resp = fetcher.fetch(index)
        resp.raise_for_status()

        json_dict = resp.json()

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
