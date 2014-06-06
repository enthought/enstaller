"""
A few utilities for python requests.
"""
from io import FileIO


class FileResponse(FileIO):
    """
    A FileIO subclass that can be used as an argument to
    HTTPAdapter.build_response method from the requests library.
    """
    def __init__(self, name, mode, closefd=True):
        super(FileResponse, self).__init__(name, mode, closefd)

        self.status = 200
        self.headers = {}
        self.reason = None

    def get_all(self, name, default):
        result = self.headers.get(name)
        if not result:
            return default
        return [result]

    def getheaders(self, name):
        return self.get_all(name, [])

    def release_conn(self):
        self.close()
