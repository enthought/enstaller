import operator
import os.path
import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from egginst.main import EggInst
from egginst.utils import compute_md5
from egginst.testing_utils import slow
from egginst.tests.common import _EGGINST_COMMON_DATA, DUMMY_EGG, create_venv, mkdtemp

from enstaller.compat import path_to_uri
from enstaller.errors import MissingPackage

from enstaller.repository import (InstalledPackageMetadata, PackageMetadata,
                                  Repository, RepositoryPackageMetadata,
                                  egg_name_to_name_version, parse_version)
from enstaller.tests.common import dummy_installed_package_factory


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
                                   "2.7")

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


class TestRepositoryPackage(unittest.TestCase):
    def test_s3index_data(self):
        # Given
        md5 = "c68bb183ae1ab47b6d67ca584957c83c"
        r_s3index_data = {
            "available": True,
            "build": 1,
            "md5": md5,
            "mtime": 0.0,
            "name": "nose",
            "packages": [],
            "product": "free",
            "python": "2.7",
            "size": 1,
            "type": "egg",
            "version": "1.3.0",

        }
        metadata = RepositoryPackageMetadata("nose-1.3.0-1.egg", "nose",
                                             "1.3.0", 1, [], "2.7", 1, md5,
                                             0.0, "free", True, "")

        # When/Then
        self.assertEqual(metadata.s3index_data, r_s3index_data)

    def test_from_egg(self):
        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")

        # When
        metadata = RepositoryPackageMetadata.from_egg(path)

        # Then
        self.assertEqual(metadata.name, "nose")
        self.assertEqual(metadata.version, "1.3.0")
        self.assertEqual(metadata.store_location, "{0}/".format(path_to_uri(_EGGINST_COMMON_DATA)))
        self.assertEqual(metadata.source_url, path_to_uri(path))


class TestInstalledPackage(unittest.TestCase):
    def test_from_meta_dir(self):
        # Given
        json_dict = {
          "arch": "amd64",
          "build": 1,
          "ctime": "Thu Apr 24 15:41:24 2014",
          "hook": False,
          "key": "VTK-5.10.1-1.egg",
          "name": "vtk",
          "osdist": "RedHat_5",
          "packages": [],
          "platform": "linux2",
          "python": "2.7",
          "type": "egg",
          "version": "5.10.1"
        }

        # When
        metadata = InstalledPackageMetadata.from_installed_meta_dict(json_dict)

        # Then
        self.assertEqual(metadata.key, "VTK-5.10.1-1.egg")

    def test_from_meta_dir_no_packages(self):
        # Given
        json_dict = {
          "arch": "amd64",
          "build": 1,
          "ctime": "Thu Apr 24 15:41:24 2014",
          "hook": False,
          "key": "VTK-5.10.1-1.egg",
          "name": "vtk",
          "osdist": "RedHat_5",
          "platform": "linux2",
          "python": "2.7",
          "type": "egg",
          "version": "5.10.1"
        }

        # When
        metadata = InstalledPackageMetadata.from_installed_meta_dict(json_dict)

        # Then
        self.assertEqual(metadata.key, "VTK-5.10.1-1.egg")
        self.assertEqual(metadata.packages, [])


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
        self.repository = Repository()
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RepositoryPackageMetadata.from_egg(path)
            self.repository.add_package(package)

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
        self.assertEqual(metadata.store_location,
                         "{0}/".format(path_to_uri(_EGGINST_COMMON_DATA)))

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
                                            "1.3.0", 1, [], "2.7")
        unavailable_package = PackageMetadata("nose-1.4.0-1.egg", "nose",
                                              "1.4.0", 1, [], "2.7")

        # When/Then
        self.assertTrue(self.repository.has_package(available_package))
        self.assertFalse(self.repository.has_package(unavailable_package))

    def test_iter_most_recent_packages(self):
        # Given
        eggs = ["nose-1.3.0-1.egg", "nose-1.2.1-1.egg"]
        repository = Repository()
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RepositoryPackageMetadata.from_egg(path)
            repository.add_package(package)

        # When
        metadata = list(repository.iter_most_recent_packages())

        # Then
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0].version, "1.3.0")

    def test_iter_packages(self):
        # Given
        eggs = ["nose-1.3.0-1.egg", "nose-1.2.1-1.egg"]
        repository = Repository()
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RepositoryPackageMetadata.from_egg(path)
            repository.add_package(package)

        # When
        metadata = list(repository.iter_packages())

        # Then
        self.assertEqual(len(metadata), 2)
        self.assertEqual(set(m.version for m in metadata),
                         set(["1.2.1", "1.3.0"]))

    @slow
    def test_from_prefix(self):
        # Given
        path = DUMMY_EGG
        with mkdtemp() as tempdir:
            create_venv(tempdir)
            installer = EggInst(path, prefix=tempdir)
            installer.install()

            # When
            repository = Repository._from_prefixes([tempdir])

            # Then
            packages = repository.find_packages("dummy")
            self.assertEqual(len(packages), 1)
            self.assertEqual(packages[0].name, "dummy")

    def test_from_empty_prefix(self):
        # Given
        with mkdtemp() as tempdir:

            # When
            repository = Repository._from_prefixes([tempdir])

            # Then
            self.assertEqual(len(list(repository.iter_packages())), 0)

    def test_delete_non_existing(self):
        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")
        to_remove = PackageMetadata.from_egg(path)
        repository = Repository()

        # When/Then
        with self.assertRaises(MissingPackage):
            repository.delete_package(to_remove)

    def test_delete_simple(self):
        # Given
        eggs = ["flake8-2.0.0-2.egg", "nose-1.3.0-1.egg", "nose-1.2.1-1.egg"]
        repository = Repository()
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RepositoryPackageMetadata.from_egg(path)
            repository.add_package(package)

        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")
        to_remove = PackageMetadata.from_egg(path)

        # When
        repository.delete_package(to_remove)

        # Then
        self.assertItemsEqual(
            [p.key for p in repository.iter_packages()],
            ["flake8-2.0.0-2.egg", "nose-1.2.1-1.egg"])

# Unittest that used to belong to Enpkg
class TestRepositoryMisc(unittest.TestCase):
    def test_find_packages_invalid_versions(self):
        # Given
        entries = [
            dummy_installed_package_factory("numpy", "1.6.1", 1),
            dummy_installed_package_factory("numpy", "1.8k", 2),
        ]
        repository = Repository()
        for entry in entries:
            repository.add_package(entry)

        # When
        packages = repository.find_packages("numpy")

        # Then
        self.assertEqual(len(packages), 2)
        self.assertItemsEqual(packages, entries)

    def test_sorted_packages_valid(self):
        # Given
        entries = [
            dummy_installed_package_factory("numpy", "1.6.1", 1),
            dummy_installed_package_factory("numpy", "1.8.0", 2),
            dummy_installed_package_factory("numpy", "1.7.1", 1),
        ]
        repository = Repository()
        for entry in entries:
            repository.add_package(entry)

        # When
        packages = repository.find_sorted_packages("numpy")

        # Then
        self.assertEqual(len(packages), 3)
        self.assertEqual([p.version for p in packages], ["1.6.1", "1.7.1",
                                                         "1.8.0"])

    def test_sorted_packages_invalid(self):
        # Given
        entries = [
            dummy_installed_package_factory("numpy", "1.6.1", 1),
            dummy_installed_package_factory("numpy", "1.8k", 2),
        ]
        repository = Repository()
        for entry in entries:
            repository.add_package(entry)

        # When
        packages = repository.find_sorted_packages("numpy")

        # Then
        self.assertEqual(len(packages), 2)
        self.assertItemsEqual([p.version for p in packages], ["1.6.1", "1.8k"])
