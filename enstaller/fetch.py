import math
import os
import sys
import hashlib
from uuid import uuid4
from os.path import basename, isdir, isfile, join

from egginst.utils import compute_md5, human_bytes, rm_rf
from enstaller.compat import close_file_or_response


class StoreResponse(object):
    def __init__(self, fp, buffsize=256):
        self._fp = fp
        self.buffsize = buffsize

    def close(self):
        close_file_or_response(self._fp)

    def iter_content(self):
        try:
            while True:
                chunk = self._fp.read(self.buffsize)
                if not chunk:
                    break
                else:
                    yield chunk
        finally:
            self.close()


class FetchAPI(object):

    def __init__(self, remote, local_dir, evt_mgr=None):
        self.remote = remote
        self.local_dir = local_dir
        self.evt_mgr = evt_mgr
        self.verbose = False

    def path(self, fn):
        return join(self.local_dir, fn)

    def size(self, key):
        """ Returns the size of value with the given key."""
        info = self.remote.get_metadata(key)
        return info["size"]

    def md5(self, key):
        """ Returns the md5 of value with the given key.

        May be None.
        """
        info = self.remote.get_metadata(key)
        return info.get("md5", None)

    def fetch(self, key, execution_aborted=None):
        """ Fetch the given key.

        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        path = self.path(key)

        size = self.size(key)
        md5 = self.md5(key)

        if size < 256:
            buffsize = 1
        else:
            buffsize = 2 ** int(math.log(size / 256.0) / math.log(2.0) + 1)

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

        response = StoreResponse(self.remote.get_data(key), buffsize)

        n = 0
        h = hashlib.new('md5')

        pp = path + '.part'
        if sys.platform == 'win32':
            rm_rf(pp)

        with progress:
            with open(pp, 'wb') as fo:
                for chunk in response.iter_content():
                    if execution_aborted is not None and execution_aborted.is_set():
                        response.close()
                        return
                    fo.write(chunk)
                    if md5:
                        h.update(chunk)
                    n += len(chunk)
                    progress(step=n)

        if md5 and h.hexdigest() != md5:
            raise ValueError("received data MD5 sums mismatch")

        if sys.platform == 'win32':
            rm_rf(path)
        os.rename(pp, path)

    def fetch_egg(self, egg, force=False, execution_aborted=None):
        """
        fetch an egg, i.e. copy or download the distribution into local dir
        force: force download or copy if MD5 mismatches
        execution_aborted: a threading.Event object which signals when the execution
            needs to be aborted, or None, if we don't want to abort the fetching at all.
        """
        if not isdir(self.local_dir):
            os.makedirs(self.local_dir)
        info = self.remote.get_metadata(egg)
        path = self.path(egg)

        # if force is used, make sure the md5 is the expected, otherwise
        # merely see if the file exists
        if isfile(path):
            if force:
                if compute_md5(path) == info.get('md5'):
                    if self.verbose:
                        print "Not refetching, %r MD5 match" % path
                    return
            else:
                if self.verbose:
                    print "Not forcing refetch, %r exists" % path
                return

        self.fetch(egg, execution_aborted)
