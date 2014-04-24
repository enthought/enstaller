from enstaller.compat import close_file_or_response


# 1024 should be reasonable for binary data. See
# https://github.com/kennethreitz/requests/issues/844 for illumanting
# discussions (especially Brandon Rhodes comments).
_DEFAULT_CHUNK_SIZE = 1024


class StoreResponse(object):
    def __init__(self, fp, size=None, md5=None, label=None):
        self._fp = fp
        self.md5 = md5
        self.size = size
        self.label = label

        if size is None or size >= _DEFAULT_CHUNK_SIZE:
            self.buffsize = _DEFAULT_CHUNK_SIZE
        else:
            self.buffsize = size

    def close(self):
        close_file_or_response(self._fp)

    def read(self):
        """
        The full content of the file object in memory
        """
        return self._fp.read()

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
