import os.path
import logging

from os.path import isfile, join

from egginst.utils import compute_md5, ensure_dir, makedirs

from enstaller.fetch_utils import checked_content
from enstaller.repository import egg_name_to_name_version
from enstaller.requests_utils import (DBCache, LocalFileAdapter,
                                      QueryPathOnlyCacheController)
from enstaller.vendor import requests
from enstaller.vendor.cachecontrol.adapter import CacheControlAdapter


logger = logging.getLogger(__name__)


class _CancelableResponse(object):
    def __init__(self, path, package_metadata, fetcher, force):
        self._path = path
        self._package_metadata = package_metadata

        self._canceled = False

        self._fetcher = fetcher
        self._force = force

    def cancel(self):
        self._canceled = True

    def __iter__(self):
        return self.iter_content()

    def iter_content(self):
        if not self.needs_to_download:
            return

        with checked_content(self._path, self._package_metadata.md5) as target:
            url = self._package_metadata.source_url
            response = self._fetcher.fetch(url)

            for chunk in response.iter_content(1024):
                if self._canceled:
                    response.close()
                    target.abort = True
                    return

                target.write(chunk)
                yield chunk

    @property
    def needs_to_download(self):
        needs_to_download = True

        if isfile(self._path):
            if self._force:
                if compute_md5(self._path) == self._package_metadata.md5:
                    logger.info("Not refetching, %r MD5 match", self._path)
                    needs_to_download = False
            else:
                logger.info("Not forcing refetch, %r exists", self._path)
                needs_to_download = False

        return needs_to_download


class URLFetcher(object):
    def __init__(self, cache_dir, auth=None, proxies=None, verify=True):
        self._auth = auth
        self.cache_dir= cache_dir
        self.verify = verify

        self._proxies = proxies or {}

        session = requests.Session()
        session.mount("file://", LocalFileAdapter())

        self._session = session

    def _enable_etag_support(self):
        uri = os.path.join(self.cache_dir, "index_cache", "index.db")
        ensure_dir(uri)
        cache = DBCache(uri)

        adapter = CacheControlAdapter(
            cache, controller_class=QueryPathOnlyCacheController)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    def fetch(self, url):
        response = self._session.get(url, stream=True, auth=self._auth,
                                     proxies=self._proxies, verify=self.verify)
        response.raise_for_status()
        return response


class DownloadManager(object):
    def __init__(self, url_fetcher, repository, auth=None):
        self._repository = repository
        self._fetcher = url_fetcher
        self.cache_directory = url_fetcher.cache_dir

        makedirs(self.cache_directory)

    def _path(self, fn):
        return join(self.cache_directory, fn)

    def iter_fetch(self, egg, force=False):
        """ Fetch the given egg using streaming.

        Parameters
        ----------
        egg : str
            An egg filename (e.g. 'numpy-1.8.0-1.egg')
        force : bool
            If force is True, will download even if the file is already in the
            download cache.

        Example
        -------
        Simple usage::

            downloader = DownloadManager(...)
            response = downloader.iter_fetch(egg)
            for chunk in response:
                pass

        Note
        ----
        Iterating over the response already writes the file at the usual
        location. This is mostly useful when you want to control cancellation
        and/or follow download progress.
        """
        name, version = egg_name_to_name_version(egg)
        package_metadata = self._repository.find_package(name, version)

        path = self._path(package_metadata.key)

        return _CancelableResponse(path, package_metadata, self._fetcher,
                                   force)

    def fetch(self, egg, force=False):
        """ Fetch the given egg.

        Parameters
        ----------
        egg : str
            An egg filename (e.g. 'numpy-1.8.0-1.egg')
        force : bool
            If force is True, will download even if the file is already in the
            download cache.
        """
        context = self.iter_fetch(egg, force)
        for _ in context:
            pass
