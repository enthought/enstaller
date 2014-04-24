import contextlib

from enstaller.compat import close_file_or_response


# 1024 should be reasonable for binary data. See
# https://github.com/kennethreitz/requests/issues/844 for illumanting
# discussions (especially Brandon Rhodes comments).
_DEFAULT_CHUNK_SIZE = 1024


class StoreResponse(object):
    """
    An abstracted response handle.

    This allows us to handle iteration in a consistent manner whether we are
    using a file-backed store or a http-backed one

    Example
    -------

    A simple memory efficient and robust (no stalled file) download would look
    as follows::

        response = StoreResponse(...)

        with atomic_rename("foo.zip") as fp:
            for chunk in response.iter_content():
                fp.write(chunk)

    """
    def __init__(self, fp, size=None, md5=None, label=None):
        self._fp = fp
        self.md5 = md5
        self.size = size
        self.label = label

        if size is None or size >= _DEFAULT_CHUNK_SIZE:
            self.default_buffsize = _DEFAULT_CHUNK_SIZE
        else:
            self.default_buffsize = size

    @property
    def closed(self):
        return self._fp.closed

    def close(self):
        close_file_or_response(self._fp)

    def read(self):
        """
        The full content of the file object in memory
        """
        with contextlib.closing(self._fp):
            return self._fp.read()

    def iter_content(self, chunk_size=None):
        """
        Iterate over the underlying content on a per-chunk basis.

        Parameters
        ----------
        chunk_size: int or None
            The chunk size if an int, or a reasonable default that depends on
            the data size (if known)

        Note
        ----
        The underlying file handle is automatically closed if the iterator is
        entirely consumed, but you need to call the close method otherwise
        """
        chunk_size = chunk_size or self.default_buffsize
        try:
            while True:
                chunk = self._fp.read(chunk_size)
                if not chunk:
                    break
                else:
                    yield chunk
        finally:
            self.close()
