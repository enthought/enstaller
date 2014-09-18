import hashlib
import contextlib

from egginst.utils import atomic_file
from enstaller.errors import InvalidChecksum


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
        self._aborted = False

    @property
    def is_aborted(self):
        return self._aborted

    @property
    def checksum(self):
        return self._h.hexdigest()

    def abort(self):
        self._aborted = True

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
    filename : str
        The path to write to
    expected_checksum : str
        The expected checksum

    Returns
    -------
    fp : MD5File
        A file-like MD5File instance.

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

        if checked_target.is_aborted:
            target.abort()
            return
        else:
            if expected_md5 != checked_target.checksum:
                raise InvalidChecksum(filename, expected_md5,
                                      checked_target.checksum)
