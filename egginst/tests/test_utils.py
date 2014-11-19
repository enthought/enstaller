import os.path
import shutil
import sys
import tempfile
import textwrap

from egginst.tests.common import create_venv, mkdtemp
from egginst.utils import (atomic_file, get_executable, parse_assignments,
                           samefile)
from egginst.vendor.six import StringIO
from egginst.vendor.six.moves import unittest
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
            parse_assignments(StringIO("EPD_auth += 2"))

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
            temp_name = fp._name
            fp.abort()

        # Then
        self.assertFalse(os.path.exists(path))
        self.assertFalse(os.path.exists(temp_name))

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


class TestSameFile(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_simple_same_file(self):
        # Given
        os.makedirs(os.path.join(self.prefix, "foo"))
        left = os.path.join(self.prefix, "bar")
        right = os.path.join(self.prefix, "foo", os.pardir, "bar")

        with open(left, "w") as fp:
            fp.write("")

        # When/Then
        self.assertTrue(samefile(left, right))

    def test_simple_not_same_file(self):
        # Given
        left = os.path.join(self.prefix, "bar")
        right = os.path.join(self.prefix, "foo")

        for path in left, right:
            with open(path, "w") as fp:
                fp.write("")

        # When/Then
        self.assertFalse(samefile(left, right))


class TestGetExecutable(unittest.TestCase):
    def test_simple(self):
        # Given
        with mkdtemp() as prefix:
            if sys.platform == "win32":
                # python.exe is in scripts because we use virtualenv
                r_executable = os.path.join(prefix, "Scripts", "python.exe")
            else:
                r_executable = os.path.join(prefix, "bin", "python")

            create_venv(prefix)

            # When
            executable = get_executable(prefix)

        # Then
        self.assertEqual(executable, r_executable)
