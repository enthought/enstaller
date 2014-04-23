import math

from enstaller.compat import close_file_or_response


class StoreResponse(object):
    def __init__(self, fp, size=None, md5=None, label=None):
        self._fp = fp
        self.md5 = md5
        self.size = size
        self.label = label

        # FIXME: not sure this makes a lof of sense
        if size is None or size < 256:
            self.buffsize = 256
        else:
            self.buffsize = 2 ** int(math.log(size / 256.0) / math.log(2.0) + 1)

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
