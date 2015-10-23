import logging

from os.path import isfile, join

from egginst.utils import checked_content, compute_md5, makedirs


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
                    target.abort()
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


class _DownloadManager(object):
    def __init__(self, url_fetcher, repository, auth=None):
        self._repository = repository
        self._fetcher = url_fetcher
        self.cache_directory = url_fetcher.cache_directory

        makedirs(self.cache_directory)

    def _path(self, fn):
        return join(self.cache_directory, fn)

    def iter_fetch(self, package, force=False):
        """ Fetch the given package using streaming.

        Parameters
        ----------
        package : PackageMetadata
            The package to fetch
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
        path = self._path(package.key)

        return _CancelableResponse(path, package, self._fetcher,
                                   force)

    def fetch(self, package, force=False):
        """ Fetch the given package.

        Parameters
        ----------
        package : PackageMetadata
            The package to fetch
        force : bool
            If force is True, will download even if the file is already in the
            download cache.
        """
        context = self.iter_fetch(package, force)
        for _ in context:
            pass
