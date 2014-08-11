import io
import json

from egginst._compat import urlparse

from egginst.progress import console_progress_manager_factory

from enstaller.fetch import URLFetcher
from enstaller.legacy_stores import parse_index
from enstaller.repository import Repository
from enstaller.requests_utils import _ResponseIterator


def _fetch_json_with_progress(resp, store_location):
    data = io.BytesIO()

    length = int(resp.headers.get("content-length", 0))
    display = _display_store_name(store_location)
    progress = console_progress_manager_factory("Fetching index", display,
                                                size=length)
    with progress:
        for chunk in _ResponseIterator(resp):
            data.write(chunk)
            progress.update(len(chunk))

    return json.loads(data.getvalue().decode("utf-8"))


def _display_store_name(store_location):
    parts = urlparse.urlsplit(store_location)
    return urlparse.urlunsplit(("", "", parts[2], parts[3], parts[4]))


def repository_factory(config):
    index_fetcher = URLFetcher(config.repository_cache, config.auth,
                               config.proxy_dict)
    index_fetcher._enable_etag_support()

    repository = Repository()
    for url, store_location in config.indices:
        resp = index_fetcher.fetch(url)
        resp.raise_for_status()

        for package in parse_index(_fetch_json_with_progress(resp,
                                                             store_location),
                                   store_location):
            repository.add_package(package)
    return repository
