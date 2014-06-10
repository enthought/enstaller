import os.path
import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import requests

from enstaller.requests_utils import FileResponse, LocalFileAdapter


class TestFileResponse(unittest.TestCase):
    def test_simple(self):
        # Given
        path = __file__
        with open(path, "rb") as fp:
            r_data = fp.read()

        resp = FileResponse(path, "rb")

        # When
        data = resp.read()

        # Then
        self.assertEqual(data, r_data)

    def test_getheaders(self):
        # Given
        resp = FileResponse(__file__, "rb")

        # When
        header = resp.getheaders("dummy")

        # Then
        self.assertEqual(header, [])

    def test_release_conn(self):
        # Given
        resp = FileResponse(__file__, "rb")

        # When
        resp.release_conn()

        # Then
        self.assertTrue(resp.closed)


class TestLocalFileAdapter(unittest.TestCase):
    def _create_file_session(self):
        session = requests.session()
        session.mount("file://", LocalFileAdapter())

        return session

    def test_simple(self):
        # Given
        session = self._create_file_session()
        with open(__file__, "rb") as fp:
            r_data = fp.read()

        # When
        resp = session.get("file://{0}".format(os.path.abspath(__file__)))
        data = resp.content

        # Then
        self.assertEqual(data, r_data)
        self.assertEqual(resp.headers["content-length"], str(os.stat(__file__).st_size))
