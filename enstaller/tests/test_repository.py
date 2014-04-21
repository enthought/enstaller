import operator
import os.path
import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from egginst.tests.common import _EGGINST_COMMON_DATA

from enstaller.errors import MissingPackage
from enstaller.store.filesystem_store import DumbFilesystemStore

from enstaller.repository import PackageMetadata, Repository, parse_version


class TestParseVersion(unittest.TestCase):
    def test_simple(self):
        # given
        version = "1.8.0-1"

        # When
        upstream, build = parse_version(version)

        # Then
        self.assertEqual(upstream, "1.8.0")
        self.assertEqual(build, 1)

    def test_invalid(self):
        # given
        version = "1.8.0"

        # When
        with self.assertRaises(ValueError):
            parse_version(version)


class TestPackage(unittest.TestCase):
    def test_repr(self):
        # Given
        metadata = PackageMetadata("nose-1.3.0-1.egg", "nose", "1.3.0", 1, 1,
                                   None)

        # When
        r = repr(metadata)

        # Then
        self.assertEqual(r, "PackageMetadata('nose-1.3.0-1', key='nose-1.3.0-1.egg')")

    def test_from_egg(self):
        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")

        # When
        metadata = PackageMetadata.from_egg(path)

        # Then
        self.assertEqual(metadata.name, "nose")
        self.assertEqual(metadata.version, "1.3.0")
        self.assertEqual(metadata.build, 1)


class TestRepository(unittest.TestCase):
    def setUp(self):
        eggs = [
            "dummy-1.0.1-1.egg",
            "dummy_with_appinst-1.0.0-1.egg",
            "dummy_with_entry_points-1.0.0-1.egg",
            "dummy_with_proxy-1.3.40-3.egg",
            "dummy_with_proxy_scripts-1.0.0-1.egg",
            "dummy_with_proxy_softlink-1.0.0-1.egg",
            "nose-1.2.1-1.egg",
            "nose-1.3.0-1.egg",
        ]
        self.store = DumbFilesystemStore(_EGGINST_COMMON_DATA, eggs)
        self.repository = Repository(self.store)

    def test_find_package(self):
        # Given/When
        metadata = self.repository.find_package("nose", "1.3.0-1")

        # Then
        self.assertEqual(metadata.name, "nose")
        self.assertEqual(metadata.version, "1.3.0")
        self.assertEqual(metadata.build, 1)

    def test_find_unavailable_package(self):
        # Given/When/Then
        with self.assertRaises(MissingPackage):
            self.repository.find_package("nono", "1.4.0-1")

    def test_find_packages(self):
        # Given/When
        metadata = list(self.repository.find_packages("nose"))
        metadata = sorted(metadata, key=operator.attrgetter("comparable_version"))

        # Then
        self.assertEqual(len(metadata), 2)

        self.assertEqual(metadata[0].version, "1.2.1")
        self.assertEqual(metadata[1].version, "1.3.0")

        self.assertEqual(metadata[0].build, 1)
        self.assertEqual(metadata[1].build, 1)

    def test_has_package(self):
        # Given
        available_package = PackageMetadata("nose-1.3.0-1.egg", "nose", "1.3.0", 1, 1, None)
        unavailable_package = PackageMetadata("nose-1.4.0-1.egg", "nose", "1.4.0", 1, 1, None)

        # When/Then
        self.assertTrue(self.repository.has_package(available_package))
        self.assertFalse(self.repository.has_package(unavailable_package))

    def test_iter_most_recent_packages(self):
        # Given
        eggs = ["nose-1.3.0-1.egg", "nose-1.2.1-1.egg"]
        store = DumbFilesystemStore(_EGGINST_COMMON_DATA, eggs)
        repository = Repository(store)

        # When
        metadata = list(repository.iter_most_recent_packages())

        # Then
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0].version, "1.3.0")
