import os.path
import shutil
import sys
import tempfile

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import requests

from enstaller.requests_utils import _ResponseIterator
from enstaller.requests_utils import FileResponse, LocalFileAdapter
from enstaller.utils import compute_md5


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


class TestResponseIterator(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def _create_file_session(self):
        session = requests.session()
        session.mount("file://", LocalFileAdapter())

        return session

    def test_simple(self):
        # Given
        session = self._create_file_session()
        source = __file__
        target = os.path.join(self.prefix, "output.dat")

        # When
        resp = session.get("file://{0}".format(os.path.abspath(source)))
        with open(target, "w") as fp:
            for chunk in _ResponseIterator(resp):
                fp.write(chunk)

        # Then
        self.assertEqual(compute_md5(target), compute_md5(source))

    def test_without_content_length(self):
        # Given
        session = self._create_file_session()
        source = __file__
        target = os.path.join(self.prefix, "output.dat")

        # When
        resp = session.get("file://{0}".format(os.path.abspath(source)))
        resp.headers.pop("content-length")
        with open(target, "w") as fp:
            for chunk in _ResponseIterator(resp):
                fp.write(chunk)

        # Then
        self.assertEqual(compute_md5(target), compute_md5(source))
