import os.path
import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from egginst.utils import compute_md5
from egginst.tests.common import (NOSE_1_3_0, SUPPORT_SYMLINK,
    ZIP_WITH_SOFTLINK, mkdtemp)
from egginst._compat import StringIO
from egginst._zipfile import ZipFile


def list_files(top):
    paths = []
    for root, dirs, files in os.walk(top):
        for f in files:
            paths.append(os.path.join(os.path.relpath(root, top), f))
    return paths

class TestZipFile(unittest.TestCase):
    def test_simple(self):
        # Given
        path = NOSE_1_3_0
        r_paths = [
            "EGG-INFO/entry_points.txt",
            "EGG-INFO/PKG-INFO",
            "EGG-INFO/spec/depend",
            "EGG-INFO/spec/summary",
            "EGG-INFO/usr/share/man/man1/nosetests.1",
        ]

        # When
        with mkdtemp() as d:
            with ZipFile(path) as zp:
                zp.extractall(d)
            paths = list_files(d)

        # Then
        self.assertItemsEqual(paths, r_paths)

    def test_extract(self):
        # Given
        path = NOSE_1_3_0
        arcname = "EGG-INFO/PKG-INFO"

        # When
        with mkdtemp() as d:
            with ZipFile(path) as zp:
                zp.extract(arcname, d)
            self.assertTrue(os.path.exists(os.path.join(d, arcname)))

    def test_extract_to(self):
        # Given
        path = NOSE_1_3_0
        arcname = "EGG-INFO/PKG-INFO"

        # When
        with mkdtemp() as d:
            with ZipFile(path) as zp:
                zp.extract_to(arcname, "FOO", d)
                extracted_data = zp.read(arcname)
            self.assertTrue(os.path.exists(os.path.join(d, "FOO")))
            self.assertEqual(compute_md5(os.path.join(d, "FOO")),
                             compute_md5(StringIO(extracted_data)))
            self.assertFalse(os.path.exists(os.path.join(d, "EGG-INFO/PKG-INFO")))

    @unittest.skipIf(not SUPPORT_SYMLINK, "this platform does not support symlink")
    def test_softlink(self):
        # Given
        path = ZIP_WITH_SOFTLINK

        # When/Then
        with mkdtemp() as d:
            with ZipFile(path) as zp:
                zp.extractall(d)
            paths = list_files(d)

            self.assertItemsEqual(paths, ["lib/foo.so.1.3", "lib/foo.so"])
            self.assertTrue(os.path.islink(os.path.join(d, "lib", "foo.so")))
