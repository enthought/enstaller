import os.path
import logging

from os.path import isfile, join

from egginst.progress import FileProgressManager, console_progress_manager_factory
from egginst.utils import compute_md5, ensure_dir, makedirs

from enstaller.fetch_utils import checked_content
from enstaller.repository import egg_name_to_name_version
from enstaller.requests_utils import (DBCache, LocalFileAdapter,
                                      QueryPathOnlyCacheController)
from enstaller.vendor import requests
from enstaller.vendor.cachecontrol.adapter import CacheControlAdapter


logger = logging.getLogger(__name__)


class _CancelableResponse(object):
    def __init__(self, path, package_metadata, fetcher, force, progress_factory):
        self._path = path
        self._package_metadata = package_metadata

        self._canceled = False
        self._progress_factory = progress_factory
        self._progress_update = None

        self._fetcher = fetcher
        self._force = force

    def progress_update(self, step):
        self._progress_update(step)

    def cancel(self):
        self._canceled = True
        # XXX: hack to not display the remaining progress bar, as the egginst
        # progress bar API does not allow for cancellation yet.
        self._progress.silent = True

    def __iter__(self):
        return self.iter_content()

    def iter_content(self):
        if not self._needs_to_download(self._package_metadata, self._force):
            return

        progress = self._progress_factory(self._package_metadata.key,
                                          self._package_metadata.size)
        self._progress = progress
        file_progress = FileProgressManager(progress)

        with file_progress:
            self._progress_update = file_progress.update
            with checked_content(self._path, self._package_metadata.md5) as target:
                url = self._package_metadata.source_url
                response = self._fetcher.fetch(url)

                for chunk in response.iter_content(1024):
                    if self._canceled:
                        response.close()
                        target.abort = True
                        return

                    target.write(chunk)
                    yield len(chunk)

    def _needs_to_download(self, package_metadata, force):
        needs_to_download = True

        if isfile(self._path):
            if force:
                if compute_md5(self._path) == package_metadata.md5:
                    logger.info("Not refetching, %r MD5 match", self._path)
                    needs_to_download = False
            else:
                logger.info("Not forcing refetch, %r exists", self._path)
                needs_to_download = False

        return needs_to_download


class URLFetcher(object):
    def __init__(self, cache_dir, auth=None, proxies=None):
        self._auth = auth
        self.cache_dir= cache_dir

        if proxies:
            self._proxies = dict((proxy_info.scheme, str(proxy_info)) for
                                 proxy_info in proxies)
        else:
            self._proxies = {}

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
        return self._session.get(url, stream=True, auth=self._auth,
                                 proxies=self._proxies)


class DownloadManager(object):
    def __init__(self, repository, cache_directory, auth=None):
        """
        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        self._repository = repository
        self._fetcher = URLFetcher(cache_directory, auth)
        self.cache_directory = cache_directory

        makedirs(self.cache_directory)

    def _path(self, fn):
        return join(self.cache_directory, fn)

    def iter_fetch(self, egg, force=False):
        name, version = egg_name_to_name_version(egg)
        package_metadata = self._repository.find_package(name, version)

        path = self._path(package_metadata.key)
        def _progress_factory(filename, installed_size):
            return console_progress_manager_factory("fetching", filename,
                                                    installed_size)

        return _CancelableResponse(path, package_metadata, self._fetcher,
                                   force, _progress_factory)

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
        for chunk_size in context:
            context.progress_update(chunk_size)
