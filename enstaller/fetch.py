import logging

from os.path import isfile, join

from egginst.progress import FileProgressManager, progress_manager_factory
from egginst.utils import atomic_file, compute_md5, makedirs

from enstaller.fetch_utils import StoreResponse, checked_content
from enstaller.legacy_stores import URLFetcher
from enstaller.repository import egg_name_to_name_version


logger = logging.getLogger(__name__)


class _CancelableResponse(object):
    def __init__(self, path, package_metadata, response):
        self._path = path
        self._package_metadata = package_metadata
        self._response = response

        self._canceled = False

    def cancel(self):
        self._canceled = True

    def iter_content(self):
        with checked_content(self._path, self._package_metadata.md5) as target:
            for chunk in self._response.iter_content():
                if self._canceled:
                    self._response.close()
                    target.abort = True
                    return

                target.write(chunk)
                yield chunk


class DownloadManager(object):
    def __init__(self, repository, cache_directory, auth=None, evt_mgr=None):
        self._repository = repository
        self._fetcher = URLFetcher(cache_directory, auth)
        self.cache_directory = cache_directory
        self.evt_mgr = evt_mgr

        makedirs(self.cache_directory)

    def _path(self, fn):
        return join(self.cache_directory, fn)

    def _iter_fetch(self, package_metadata):
        response = StoreResponse(self._fetcher.open(package_metadata.source_url),
                                 package_metadata.size, package_metadata.md5,
                                 package_metadata.key)

        path = self._path(package_metadata.key)
        return _CancelableResponse(path, package_metadata, response)

    def _fetch(self, package_metadata, execution_aborted=None):
        """ Fetch the given key.

        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        progress = progress_manager_factory("fetching", package_metadata.key,
                                            package_metadata.size,
                                            self.evt_mgr, self)

        with FileProgressManager(progress) as progress:
            context = self._iter_fetch(package_metadata)
            for chunk in context.iter_content():
                if execution_aborted is not None and execution_aborted.is_set():
                    context.cancel()
                    return
                progress.update(len(chunk))

    def _needs_to_download(self, package_metadata, force):
        needs_to_download = True
        path = self._path(package_metadata.key)

        if isfile(path):
            if force:
                if compute_md5(path) == package_metadata.md5:
                    logger.info("Not refetching, %r MD5 match", path)
                    needs_to_download = False
            else:
                logger.info("Not forcing refetch, %r exists", path)
                needs_to_download = False

        return needs_to_download

    def fetch_egg(self, egg, force=False, execution_aborted=None):
        """
        fetch an egg, i.e. copy or download the distribution into local dir
        force: force download or copy if MD5 mismatches
        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        name, version = egg_name_to_name_version(egg)
        package_metadata = self._repository.find_package(name, version)

        if self._needs_to_download(package_metadata, force):
            self._fetch(package_metadata, execution_aborted)
