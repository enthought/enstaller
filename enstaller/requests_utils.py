"""
A few utilities for python requests.
"""
import os

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
        stat_info = os.stat(path)

        response = self.build_response(request, FileResponse(path, "rb"))
        response.headers["content-length"] = str(stat_info.st_size)
        return response

    def send(self, request, stream=False, timeout=None,
             verify=True, cert=None, proxies=None):

        return self.build_response_from_file(request, stream)


class _ResponseIterator(object):
    """
    A simple iterator on top of a requests response

    It supports the `len` protocol so that packages such as click can show an
    ETA when fetching by chunk.

    Example
    -------
    >>> resp = requests.get("http://acme.com", stream=True)
    >>> for chunk in _ResponseIterator(resp):
        print len(chunk)
    """
    def __init__(self, response):
        self._response = response
        self._size = int(self._response.headers.get("content-length", 0))
        self._chunk_size = 1024

    def __iter__(self):
        self._iter = self._response.iter_content(self._chunk_size)
        return self

    def next(self):
        return self._iter.next()

    def __len__(self):
        return int(self._size / self._chunk_size + 1)
