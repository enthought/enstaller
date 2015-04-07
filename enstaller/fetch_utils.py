import hashlib
import contextlib

from egginst.utils import atomic_file
from enstaller.errors import EnstallerException, InvalidChecksum


_CHECKSUM_KIND_TO_HASHER = {
    'md5': hashlib.md5,
    'sha256': hashlib.sha256,
}


class Checksummer(object):
    def __init__(self, fp, hasher=None):
        """
        A simple file object wrapper that computes a checksum only when data
        are being written

        Parameters
        ----------
        fp: file object-like
            The file object to wrap.
        hasher: object
            One of the hashlib object (e.g. hashlib.md5(), hashlib.sha256(),
            etc...)
        """
        self._fp = fp
        self._h = hasher or hashlib.md5()
        self._aborted = False

    def hexdigest(self):
        return self._h.hexdigest()

    @property
    def is_aborted(self):
        return self._aborted

    def abort(self):
        self._aborted = True

    def write(self, data):
        """
        Write the given data buffer to the underlying file.
        """
        self._fp.write(data)
        self._h.update(data)


@contextlib.contextmanager
def checked_content(filename, expected_checksum, checksum_kind='md5'):
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
    fp : Checksummer
        A file-like instance.

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
    hasher = _CHECKSUM_KIND_TO_HASHER.get(checksum_kind)
    if hasher is None:
        msg = "Invalid checksum kind: {0!r}"
        raise EnstallerException(msg.format(checksum_kind))

    with atomic_file(filename) as target:
        checked_target = Checksummer(target, hasher())
        yield checked_target

        if checked_target.is_aborted:
            target.abort()
            return
        else:
            actual_checksum = checked_target.hexdigest()
            if expected_checksum != actual_checksum:
                raise InvalidChecksum(filename, expected_checksum,
                                      actual_checksum)
