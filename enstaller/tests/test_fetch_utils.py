import hashlib
import os.path
import shutil
import tempfile

from egginst.vendor.six.moves import unittest

from enstaller.errors import InvalidChecksum
from enstaller.fetch_utils import (MD5File, checked_content)
from enstaller.utils import compute_md5


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
                fp.write(b"")

    def test_abort(self):
        # Given
        data = b"data"
        checksum = hashlib.md5(data).hexdigest()
        path = os.path.join(self.tempdir, "foo.data")

        # When/Then
        with checked_content(path, checksum) as fp:
            fp.abort()
