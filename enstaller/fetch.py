import contextlib
import hashlib
import os
import sys

from uuid import uuid4
from os.path import basename, isdir, isfile, join

from egginst.utils import compute_md5, human_bytes, rm_rf
from enstaller.repository import egg_name_to_name_version


class _FileStore(object):
    def __init__(self, filename, md5=None):
        self.filename = filename
        self.md5 = md5

        self._h = hashlib.md5()

        self._pp = self.filename + ".part"
        self._fo = None

    def _init(self):
        if sys.platform == 'win32':
            rm_rf(self._pp)
        self._fo = open(self._pp, "wb")

    def _close(self):
        self._fo.close()

    def write_chunk(self, chunk):
        self._fo.write(chunk)
        if self.md5:
            self._h.update(chunk)

    def finalize(self):
        """
        Write the data in the configured output, after having checked for the
        md5 (if given in the init function).
        """
        if self.md5 and self._h.hexdigest() != self.md5:
            raise ValueError("received data MD5 sums mismatch")

        if sys.platform == 'win32':
            rm_rf(self.filename)
        os.rename(self._pp, self.filename)


@contextlib.contextmanager
def filestore_manager(filename, md5=None):
    f = _FileStore(filename, md5)
    f._init()
    try:
        yield f
    finally:
        f._close()


class FetchAPI(object):

    def __init__(self, repository, local_dir, evt_mgr=None):
        self.repository = repository
        self.local_dir = local_dir
        self.evt_mgr = evt_mgr
        self.verbose = False

    def path(self, fn):
        return join(self.local_dir, fn)

    def size(self, name, version):
        """ Returns the size of value for the package with the given name,
        version."""
        info = self.repository.find_package(name, version)
        return info.size

    def md5(self, name, version):
        """ Returns the md5 of value with the given key.

        May be None.
        """
        info = self.repository.find_package(name, version)
        return info.md5

    def fetch(self, key, execution_aborted=None):
        """ Fetch the given key.

        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        name, version = egg_name_to_name_version(key)

        package = self.repository.find_package(name, version)

        path = self.path(key)
        size = package.size

        if self.evt_mgr:
            from encore.events.api import ProgressManager
        else:
            from egginst.console import ProgressManager
        progress = ProgressManager(
                self.evt_mgr, source=self,
                operation_id=uuid4(),
                message="fetching",
                steps=size,
                # ---
                progress_type="fetching", filename=basename(path),
                disp_amount=human_bytes(size),
                super_id=getattr(self, 'super_id', None))

        response = self.repository.fetch_from_package(package)
        n = 0
        with progress:
            md5 = package.md5
            with filestore_manager(path, md5) as target:
                for chunk in response.iter_content():
                    if execution_aborted is not None and execution_aborted.is_set():
                        response.close()
                        return
                    target.write_chunk(chunk)
                    n += len(chunk)
                    progress(step=n)

        target.finalize()

    def fetch_egg(self, egg, force=False, execution_aborted=None):
        """
        fetch an egg, i.e. copy or download the distribution into local dir
        force: force download or copy if MD5 mismatches
        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        if not isdir(self.local_dir):
            os.makedirs(self.local_dir)
        name, version = egg_name_to_name_version(egg)
        package_metadata = self.repository.find_package(name, version)

        path = self.path(egg)

        # if force is used, make sure the md5 is the expected, otherwise
        # merely see if the file exists
        if isfile(path):
            if force:
                if compute_md5(path) == package_metadata.md5:
                    if self.verbose:
                        print "Not refetching, %r MD5 match" % path
                    return
            else:
                if self.verbose:
                    print "Not forcing refetch, %r exists" % path
                return

        self.fetch(package_metadata.key, execution_aborted)
