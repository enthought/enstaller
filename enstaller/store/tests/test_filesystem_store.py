import os.path
import sys

from okonomiyaki.repositories.enpkg import EnpkgS3IndexEntry

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from egginst.utils import compute_md5
from enstaller.store.filesystem_store import DumbFilesystemStore

from egginst.tests.common import _EGGINST_COMMON_DATA, mkdtemp


class TestDumpyFilesystemStore(unittest.TestCase):
    def _write_data(self, source_fp, target_path):
        with open(target_path, "wb") as target:
            target.write(source_fp.read())
        source_fp.close()

    def test_connected_api(self):
        # Given
        store = DumbFilesystemStore(_EGGINST_COMMON_DATA, ["nose-1.3.0-1.egg"])

        # When
        store.connect((None, None))

        # Then
        self.assertTrue(store.is_connected())
        self.assertEqual(store.info(), {"root": _EGGINST_COMMON_DATA})

    def test_query_simple(self):
        # Given
        store = DumbFilesystemStore(_EGGINST_COMMON_DATA, ["nose-1.3.0-1.egg"])

        # When
        metadata = dict(store.query(name="nose"))

        # Then
        self.assertItemsEqual(metadata.keys(), ["nose-1.3.0-1.egg"])

        # When
        metadata = dict(store.query(version="1.3.0"))

        # Then
        self.assertItemsEqual(metadata.keys(), ["nose-1.3.0-1.egg"])

    def test_query_simple_missing(self):
        # Given
        store = DumbFilesystemStore(_EGGINST_COMMON_DATA, ["nose-1.3.0-1.egg"])

        # When
        metadata = dict(store.query(name="nono"))

        # Then
        self.assertItemsEqual(metadata.keys(), [])

    def test_exists(self):
        # Given
        store = DumbFilesystemStore(_EGGINST_COMMON_DATA, ["nose-1.3.0-1.egg"])

        # When/Then
        self.assertTrue(store.exists("nose-1.3.0-1.egg"))
        self.assertFalse(store.exists("nose-1.3.0-2.egg"))

    def test_get_metadata(self):
        # Given
        egg = "nose-1.3.0-1.egg"
        root = _EGGINST_COMMON_DATA
        r_metadata = EnpkgS3IndexEntry.from_egg(os.path.join(root, egg),
                                                product=None,
                                                available=True).s3index_data
        store = DumbFilesystemStore(root, [egg])

        # When
        metadata = store.get_metadata("nose-1.3.0-1.egg")

        # Then
        self.assertEqual(metadata, r_metadata)

    def test_get_data(self):
        # Given
        egg = "nose-1.3.0-1.egg"
        root = _EGGINST_COMMON_DATA
        store = DumbFilesystemStore(root, [egg])

        # When
        with mkdtemp() as d:
            path = os.path.join(d, "some_file.egg")
            source = store.get_data("nose-1.3.0-1.egg")
            self._write_data(source, path)
            md5 = compute_md5(path)

        # Then
        self.assertEqual(md5, compute_md5(os.path.join(root, egg)))

        # When/Then
        with self.assertRaises(KeyError):
            store.get_data("nono-1.0.0-1.egg")

    def test_get(self):
        # Given
        egg = "nose-1.3.0-1.egg"
        root = _EGGINST_COMMON_DATA
        r_metadata = EnpkgS3IndexEntry.from_egg(os.path.join(root, egg),
                                                product=None,
                                                available=True).s3index_data
        store = DumbFilesystemStore(root, [egg])

        # When
        source, metadata = store.get("nose-1.3.0-1.egg")

        with mkdtemp() as d:
            path = os.path.join(d, "some_file.egg")
            self._write_data(source, path)
            md5 = compute_md5(path)

        # Then
        self.assertEqual(md5, compute_md5(os.path.join(root, egg)))
        self.assertEqual(metadata, r_metadata)
