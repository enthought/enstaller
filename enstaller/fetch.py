import contextlib
import hashlib
import logging

from os.path import isfile, join

from egginst.progress import FileProgressManager, progress_manager_factory
from egginst.utils import atomic_file, compute_md5, makedirs

from enstaller.errors import InvalidChecksum
from enstaller.fetch_utils import StoreResponse
from enstaller.legacy_stores import URLFetcher
from enstaller.repository import egg_name_to_name_version


logger = logging.getLogger(__name__)


class MD5File(object):
    def __init__(self, fp):
        """
        A simple file object wrapper that computes a md5 checksum only when data
        are being written

        Parameters
        ----------
        fp: file object-like
            The file object to wrap.
        """
        self._fp = fp
        self._h = hashlib.md5()
        self.abort = False

    @property
    def checksum(self):
        return self._h.hexdigest()

    def write(self, data):
        """
        Write the given data buffer to the underlying file.
        """
        self._fp.write(data)
        self._h.update(data)


@contextlib.contextmanager
def checked_content(filename, expected_md5):
    """
    A simple context manager ensure data written to filename match the given
    md5.

    Parameters
    ----------
    filename: str
        The path to write to
    expected_checksum: str
        The expected checksum

    Returns
    -------
    fp: MD5File instance
        A file-like object.

    Example
    -------
    A simple example::

        with checked_content("foo.bin", expected_md5) as fp:
            fp.write(data)
        # An InvalidChecksum will be raised if the checksum does not match
        # expected_md5

    The checksum may be disabled by setting up abort to fp::

        with checked_content("foo.bin", expected_md5) as fp:
            fp.write(data)
            fp.abort = True
            # no checksum is getting validated
    """
    with atomic_file(filename) as target:
        checked_target = MD5File(target)
        yield checked_target

        if checked_target.abort:
            target.abort = True
            return
        else:
            if expected_md5 != checked_target.checksum:
                raise InvalidChecksum(filename, expected_md5, checked_target.checksum)


class DownloadManager(object):
    def __init__(self, repository, local_dir, auth=None, evt_mgr=None):
        self._repository = repository
        self._fetcher = URLFetcher(local_dir, auth)
        self.local_dir = local_dir
        self.evt_mgr = evt_mgr

        makedirs(self.local_dir)

    def _path(self, fn):
        return join(self.local_dir, fn)

    def _fetch(self, package_metadata, execution_aborted=None):
        """ Fetch the given key.

        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        progress = progress_manager_factory("fetching", package_metadata.key,
                                            package_metadata.size,
                                            self.evt_mgr, self)

        response = StoreResponse(self._fetcher.open(package_metadata.source_url),
                                 package_metadata.size, package_metadata.md5,
                                 package_metadata.key)

        with FileProgressManager(progress) as progress:
            path = self._path(package_metadata.key)
            with checked_content(path, package_metadata.md5) as target:
                for chunk in response.iter_content():
                    if execution_aborted is not None and execution_aborted.is_set():
                        response.close()
                        target.abort = True
                        return

                    target.write(chunk)
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
