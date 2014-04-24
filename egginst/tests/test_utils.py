import os.path
import shutil
import sys
import tempfile
import textwrap

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from cStringIO import StringIO

from egginst.utils import atomic_file, parse_assignments
from enstaller.errors import InvalidFormat


class TestParseAssignments(unittest.TestCase):
    def test_parse_simple(self):
        r_data = {"IndexedRepos": ["http://acme.com/{SUBDIR}"],
                  "webservice_entry_point": "http://acme.com/eggs/{PLATFORM}/"}

        s = textwrap.dedent("""\
        IndexedRepos = [
            "http://acme.com/{SUBDIR}",
        ]
        webservice_entry_point = "http://acme.com/eggs/{PLATFORM}/"
        """)

        data = parse_assignments(StringIO(s))
        self.assertEqual(data, r_data)

    def test_parse_simple_invalid_file(self):
        with self.assertRaises(InvalidFormat):
            parse_assignments(StringIO("EPD_auth = 1 + 2"))

        with self.assertRaises(InvalidFormat):
            parse_assignments(StringIO("1 + 2"))

class TestAtomicFile(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_simple(self):
        # Given
        r_content = b"some data"
        path = os.path.join(self.tempdir, "some_data.bin")

        # When
        with atomic_file(path) as fp:
            fp.write(r_content)

        # Then
        self.assertTrue(os.path.exists(path))
        with open(path, "rb") as fp:
            content = fp.read()
        self.assertEqual(content, r_content)

    def test_failure(self):
        # Given
        r_content = b"some data"
        path = os.path.join(self.tempdir, "some_data.bin")

        # When
        try:
            with atomic_file(path) as fp:
                fp.write(r_content[:2])
                raise KeyboardInterrupt()
        except BaseException:
            pass

        # Then
        self.assertFalse(os.path.exists(path))

    def test_abort(self):
        # Given
        r_content = b"some data"
        path = os.path.join(self.tempdir, "some_data.bin")

        # When
        with atomic_file(path) as fp:
            fp.write(r_content[:2])
            fp.abort = True

        # Then
        self.assertFalse(os.path.exists(path))

    def test_exists(self):
        # Given
        r_content = b"some data"
        path = os.path.join(self.tempdir, "some_data.bin")
        with open(path, "wb") as fp:
            fp.write(b"nono")

        # When
        with atomic_file(path) as fp:
            fp.write(r_content)

        # Then
        self.assertTrue(os.path.exists(path))
        with open(path, "rb") as fp:
            content = fp.read()
        self.assertEqual(content, r_content)

    def test_exists_with_failure(self):
        # Given
        r_content = b"nono"
        path = os.path.join(self.tempdir, "some_data.bin")
        with open(path, "wb") as fp:
            fp.write(r_content)

        # When
        try:
            with atomic_file(path) as fp:
                fp.write(b"some data")
                raise ValueError("some random failure")
        except BaseException:
            pass

        # Then
        self.assertTrue(os.path.exists(path))
        with open(path, "rb") as fp:
            content = fp.read()
        self.assertEqual(content, r_content)
