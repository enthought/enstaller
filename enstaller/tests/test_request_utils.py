import os.path
import sqlite3
import tempfile

from egginst.utils import rm_rf
from egginst.vendor.six.moves import unittest

from enstaller.requests_utils import _ResponseIterator
from enstaller.requests_utils import DBCache, FileResponse, LocalFileAdapter
from enstaller.utils import compute_md5
from enstaller.vendor import requests


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
        rm_rf(self.prefix)

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
        with open(target, "wb") as fp:
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
        with open(target, "wb") as fp:
            for chunk in _ResponseIterator(resp):
                fp.write(chunk)

        # Then
        self.assertEqual(compute_md5(target), compute_md5(source))


class TestDBCache(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        rm_rf(self.prefix)

    def test_simple(self):
        # Given
        uri = os.path.join(self.prefix, "foo.db")
        cache = DBCache(uri)
        r_value = {"bar": "fubar"}

        # When
        cache.set("foo", r_value)
        value = cache.get("foo")

        # Then
        self.assertEqual(value, r_value)

        # When
        cache.delete("foo")
        value = cache.get("foo")

        # Then
        self.assertIsNone(value)

        # When/Then
        # Ensure we don't raise an exception when deleting twice
        cache.delete("foo")

    def test_simple_cannot_create_db(self):
        # Given
        uri = os.path.join(self.prefix, "foo.db")
        with open(uri, "wb") as fp:
            fp.write(b"")
        os.chmod(uri, 0o500)

        cache = DBCache(uri)
        r_value = {"bar": "fubar"}

        # When
        cache.set("foo", r_value)
        value = cache.get("foo")

        # Then
        self.assertIsNone(value)

    def _create_invalid_table(self, uri):
        cx = sqlite3.Connection(uri)
        cx.execute("""\
CREATE TABLE queue
(
    id INTEGER PRIMARY KEY AUTOINCREMENT
);""")

    def test_simple_invalid_db(self):
        # Given
        uri = os.path.join(self.prefix, "foo.db")
        self._create_invalid_table(uri)

        cache = DBCache(uri)

        # When
        cache.set("foo", "bar")
        value = cache.get("foo")

        # Then
        self.assertIsNone(value)

        # When/Then
        cache.delete("foo")
