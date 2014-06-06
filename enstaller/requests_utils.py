"""
A few utilities for python requests.
"""
from io import FileIO

import requests

from enstaller.utils import uri_to_path


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


class LocalFileAdapter(requests.adapters.HTTPAdapter):
    """
    A requests adapter to support local file IO.

    Example
    -------

    session = requests.session()
    session.mount("file://", LocalFileAdapter())

    session.get("file:///bin/ls")
    """
    def build_response_from_file(self, request, stream):
        path = uri_to_path(request.url)

        from enstaller.requests_utils import FileResponse
        return self.build_response(request, FileResponse(path, "rb"))

    def send(self, request, stream=False, timeout=None,
             verify=True, cert=None, proxies=None):

        return self.build_response_from_file(request, stream)
