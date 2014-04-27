import hashlib
import logging
import os

from uuid import uuid4
from os.path import basename, isdir, isfile, join

from egginst.utils import atomic_file, compute_md5, human_bytes, makedirs

from enstaller.errors import EnstallerException
from enstaller.repository import egg_name_to_name_version


logger = logging.getLogger(__name__)


class _MD5File(object):
    def __init__(self, fp):
        self._fp = fp
        self._h = hashlib.md5()

    @property
    def checksum(self):
        return self._h.hexdigest()

    def write(self, data):
        self._fp.write(data)
        self._h.update(data)


class FetchAPI(object):

    def __init__(self, repository, local_dir, evt_mgr=None):
        self.repository = repository
        self.local_dir = local_dir
        self.evt_mgr = evt_mgr

        makedirs(self.local_dir)

    def path(self, fn):
        return join(self.local_dir, fn)

    def fetch(self, key, execution_aborted=None):
        """ Fetch the given key.

        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        name, version = egg_name_to_name_version(key)
        package = self.repository.find_package(name, version)

        if self.evt_mgr:
            from encore.events.api import ProgressManager
        else:
            from egginst.console import ProgressManager
        progress = ProgressManager(
                self.evt_mgr, source=self,
                operation_id=uuid4(),
                message="fetching",
                steps=package.size,
                # ---
                progress_type="fetching", filename=key,
                disp_amount=human_bytes(package.size),
                super_id=getattr(self, 'super_id', None))

        response = self.repository.fetch_from_package(package)
        n = 0
        with progress:
            path = self.path(key)
            with atomic_file(path) as _target:
                target = _MD5File(_target)
                for chunk in response.iter_content():
                    if execution_aborted is not None and execution_aborted.is_set():
                        response.close()
                        _target.abort = True
                        return

                    target.write(chunk)
                    n += len(chunk)
                    progress(step=n)

                if package.md5 != target.checksum:
                    template = "Checksum mismatch for {0!r}: received {1!r} " \
                               "(expected {2!r})"
                    raise EnstallerException(template.format(path, package.md5,
                                                             target.checksum))

    def fetch_egg(self, egg, force=False, execution_aborted=None):
        """
        fetch an egg, i.e. copy or download the distribution into local dir
        force: force download or copy if MD5 mismatches
        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        name, version = egg_name_to_name_version(egg)
        package_metadata = self.repository.find_package(name, version)

        path = self.path(egg)

        # if force is used, make sure the md5 is the expected, otherwise
        # merely see if the file exists
        if isfile(path):
            if force:
                if compute_md5(path) == package_metadata.md5:
                    logger.info("Not refetching, %r MD5 match", path)
                    return
            else:
                logger.info("Not forcing refetch, %r exists", path)
                return

        self.fetch(package_metadata.key, execution_aborted)
