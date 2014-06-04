import hashlib
import os.path
import shutil
import sys
import tempfile

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from egginst._compat import BytesIO

from enstaller.errors import InvalidChecksum
from enstaller.fetch_utils import (_DEFAULT_CHUNK_SIZE, MD5File, StoreResponse,
                                   checked_content)
from enstaller.utils import compute_md5

class TestStoreResponse(unittest.TestCase):
    def test_buffsize(self):
        # Given
        response = StoreResponse(BytesIO())

        # When/Then
        self.assertEqual(response.default_buffsize, _DEFAULT_CHUNK_SIZE)

        # Given
        response = StoreResponse(BytesIO(), 1)

        # When/Then
        self.assertEqual(response.default_buffsize, 1)

        # Given
        response = StoreResponse(BytesIO(), 2**24)

        # When/Then
        self.assertEqual(response.default_buffsize, _DEFAULT_CHUNK_SIZE)

    def test_full_read(self):
        # Given
        r_content = b"some data"
        fp = BytesIO(r_content)
        response = StoreResponse(fp)

        # When
        data = response.read()

        # Then
        self.assertEqual(data, r_content)
        self.assertTrue(response.closed)

    def test_chunk_read(self):
        # Given
        r_content = b"some data" * _DEFAULT_CHUNK_SIZE
        fp = BytesIO(r_content)
        response = StoreResponse(fp)

        # When
        out = BytesIO()
        for chunk in response.iter_content():
            out.write(chunk)

        # Then
        self.assertEqual(out.getvalue(), r_content)
        self.assertTrue(response.closed)


class TestMD5File(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _write_content(self, filename, data):
        with open(filename, "wb") as fp:
            fp.write(data)

    def test_simple(self):
        # Given
        source = os.path.join(self.tempdir, "source.data")
        self._write_content(source, b"data")

        # When
        target = os.path.join(self.tempdir, "target.data")
        with open(target, "wb") as _fp:
            fp = MD5File(_fp)
            fp.write(b"data")

        # Then
        self.assertEqual(fp.checksum, compute_md5(target))
        self.assertEqual(compute_md5(target), compute_md5(source))


class TestCheckedContent(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _write_content(self, filename, data):
        with open(filename, "wb") as fp:
            fp.write(data)

    def test_simple(self):
        # Given
        data = b"data"
        checksum = hashlib.md5(data).hexdigest()
        path = os.path.join(self.tempdir, "foo.data")

        # When/Then
        with checked_content(path, checksum) as fp:
            fp.write(data)

    def test_invalid_checksum(self):
        # Given
        data = b"data"
        checksum = hashlib.md5(data).hexdigest()
        path = os.path.join(self.tempdir, "foo.data")

        # When/Then
        with self.assertRaises(InvalidChecksum):
            with checked_content(path, checksum) as fp:
                fp.write("")

    def test_abort(self):
        # Given
        data = b"data"
        checksum = hashlib.md5(data).hexdigest()
        path = os.path.join(self.tempdir, "foo.data")

        # When/Then
        with checked_content(path, checksum) as fp:
            fp.abort = True
