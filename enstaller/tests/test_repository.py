import operator
import os.path
import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from egginst.utils import compute_md5
from egginst.tests.common import _EGGINST_COMMON_DATA, mkdtemp

from enstaller.errors import MissingPackage
from enstaller.store.filesystem_store import DumbFilesystemStore

from enstaller.repository import (PackageMetadata, Repository,
                                  egg_name_to_name_version, parse_version)


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


class TestEggNameToNameVersion(unittest.TestCase):
    def test_simple(self):
        # given
        egg_name = "numpy-1.8.0-1.egg"

        # When
        name, version = egg_name_to_name_version(egg_name)

        # Then
        self.assertEqual(name, "numpy")
        self.assertEqual(version, "1.8.0-1")

    def test_simple_uppercase(self):
        # given
        egg_name = "MKL-10.3-1.egg"

        # When
        name, version = egg_name_to_name_version(egg_name)

        # Then
        self.assertEqual(name, "mkl")
        self.assertEqual(version, "10.3-1")

    def test_invalid(self):
        # given
        egg_name = "nono"

        # When
        with self.assertRaises(ValueError):
            egg_name_to_name_version(egg_name)


class TestPackage(unittest.TestCase):
    def test_repr(self):
        # Given
        metadata = PackageMetadata("nose-1.3.0-1.egg", "nose", "1.3.0", 1, [],
                                   "2.7", 1, None)

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
            "nose-1.3.0-2.egg",
        ]
        self.store = DumbFilesystemStore(_EGGINST_COMMON_DATA, eggs)
        self.repository = Repository(self.store)

    def test_find_package(self):
        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")

        # When
        metadata = self.repository.find_package("nose", "1.3.0-1")

        # Then
        self.assertEqual(metadata.key, "nose-1.3.0-1.egg")

        self.assertEqual(metadata.name, "nose")
        self.assertEqual(metadata.version, "1.3.0")
        self.assertEqual(metadata.build, 1)

        self.assertEqual(metadata.packages, [])
        self.assertEqual(metadata.python, "2.7")

        self.assertEqual(metadata.available, True)
        self.assertEqual(metadata.store_location, _EGGINST_COMMON_DATA)

        self.assertEqual(metadata.size, os.path.getsize(path))
        self.assertEqual(metadata.md5, compute_md5(path))

        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-2.egg")

        # When
        metadata = self.repository.find_package("nose", "1.3.0-2")

        # Then
        self.assertEqual(metadata.key, "nose-1.3.0-2.egg")

        self.assertEqual(metadata.name, "nose")
        self.assertEqual(metadata.version, "1.3.0")
        self.assertEqual(metadata.build, 2)

    def test_find_unavailable_package(self):
        # Given/When/Then
        with self.assertRaises(MissingPackage):
            self.repository.find_package("nono", "1.4.0-1")

    def test_find_packages(self):
        # Given/When
        metadata = list(self.repository.find_packages("nose"))
        metadata = sorted(metadata, key=operator.attrgetter("comparable_version"))

        # Then
        self.assertEqual(len(metadata), 3)

        self.assertEqual(metadata[0].version, "1.2.1")
        self.assertEqual(metadata[1].version, "1.3.0")
        self.assertEqual(metadata[2].version, "1.3.0")

        self.assertEqual(metadata[0].build, 1)
        self.assertEqual(metadata[1].build, 1)
        self.assertEqual(metadata[2].build, 2)

    def test_find_packages_with_version(self):
        # Given/When
        metadata = list(self.repository.find_packages("nose", "1.3.0-1"))

        # Then
        self.assertEqual(len(metadata), 1)

        self.assertEqual(metadata[0].version, "1.3.0")
        self.assertEqual(metadata[0].build, 1)

    def test_has_package(self):
        # Given
        available_package = PackageMetadata("nose-1.3.0-1.egg", "nose",
                                            "1.3.0", [], "2.7", 1, 1, None)
        unavailable_package = PackageMetadata("nose-1.4.0-1.egg", "nose",
                                              "1.4.0", [], "2.7", 1, 1, None)

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

    def test_iter_packages(self):
        # Given
        eggs = ["nose-1.3.0-1.egg", "nose-1.2.1-1.egg"]
        store = DumbFilesystemStore(_EGGINST_COMMON_DATA, eggs)
        repository = Repository(store)

        # When
        metadata = list(repository.iter_packages())

        # Then
        self.assertEqual(len(metadata), 2)
        self.assertEqual(set(m.version for m in metadata),
                         set(["1.2.1", "1.3.0"]))

    def test_connect(self):
        # Given
        store = mock.Mock()
        store.connect = mock.Mock()
        store.is_connected = False

        # When
        repository = Repository(store)
        repository.connect((None, None))

        # Then
        self.assertTrue(store.connect.called)

    def test_fetch(self):
        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")
        metadata = PackageMetadata.from_egg(path)

        # When
        resp = self.repository.fetch_from_package(metadata)
        try:
            with mkdtemp() as d:
                target_path = os.path.join(d, "foo.egg")
                with open(target_path, "wb") as target:
                    target.write(resp.read())
                resp.close()
                md5 = compute_md5(target_path)
        finally:
            resp.close()

        # Then
        self.assertEqual(md5, metadata.md5)
