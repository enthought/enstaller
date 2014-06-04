import logging

from os.path import isfile, join

from egginst.progress import FileProgressManager, progress_manager_factory
from egginst.utils import compute_md5, makedirs

from enstaller.fetch_utils import StoreResponse, checked_content
from enstaller.legacy_stores import URLFetcher
from enstaller.repository import egg_name_to_name_version


logger = logging.getLogger(__name__)

class _CancelableResponse(object):
    def __init__(self, path, package_metadata, fetcher, force, progress_factory):
        self._path = path
        self._package_metadata = package_metadata

        self._canceled = False
        self._progress_factory = progress_factory

        self._fetcher = fetcher
        self._force = force

    def progress_update(self, step):
        self._progress(step)

    def cancel(self):
        self._canceled = True

    def __iter__(self):
        return self.iter_content()

    def iter_content(self):
        if not self._needs_to_download(self._package_metadata, self._force):
            return

        progress = self._progress_factory(self._package_metadata.key,
                                          self._package_metadata.size)
        file_progress = FileProgressManager(progress)

        with file_progress:
            self._progress = file_progress.update
            with checked_content(self._path, self._package_metadata.md5) as target:
                response = StoreResponse(
                    self._fetcher.open(self._package_metadata.source_url),
                    self._package_metadata.size, self._package_metadata.md5,
                    self._package_metadata.key)

                for chunk in response.iter_content():
                    if self._canceled:
                        self._response.close()
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


class DownloadManager(object):
    def __init__(self, repository, cache_directory, auth=None, evt_mgr=None,
                 execution_aborted=None):
        """
        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        self._repository = repository
        self._fetcher = URLFetcher(cache_directory, auth)
        self.cache_directory = cache_directory
        self.evt_mgr = evt_mgr

        makedirs(self.cache_directory)

        self._execution_aborted = execution_aborted

    def _path(self, fn):
        return join(self.cache_directory, fn)

    def iter_fetch(self, egg, force=False):
        name, version = egg_name_to_name_version(egg)
        package_metadata = self._repository.find_package(name, version)

        path = self._path(package_metadata.key)
        def _progress_factory(filename, installed_size):
            return progress_manager_factory("fetching", filename,
                                            installed_size, self.evt_mgr, self)

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
            if self._execution_aborted is not None \
               and self._execution_aborted.is_set():
                context.cancel()
                return
            context.progress_update(chunk_size)
