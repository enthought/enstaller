import os.path
import time

from egginst.tests.common import _EGGINST_COMMON_DATA
from egginst.vendor.six.moves import unittest

from enstaller.compat import path_to_uri
from enstaller.package import (InstalledPackageMetadata, PackageMetadata,
                               RemotePackageMetadata,
                               egg_name_to_name_version)
from enstaller.repository_info import BroodRepositoryInfo, FSRepositoryInfo
from enstaller.utils import PY_VER
from enstaller.versions.enpkg import EnpkgVersion


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
    def test_eq(self):
        # Given
        V = EnpkgVersion.from_string
        package1 = PackageMetadata("nose-1.3.0-1.egg", "nose",
                                   V("1.3.0-1"), [], "2.7")
        package2 = PackageMetadata("nose-1.3.0-1.egg", "nose",
                                   V("1.3.0-1"), [], "2.7")
        package3 = PackageMetadata("nose-1.3.0-1.egg", "nose",
                                   V("1.3.0-1"), [], "2.8")

        # Then
        self.assertTrue(package1 == package2)
        self.assertTrue(hash(package1) == hash(package2))
        self.assertFalse(package1 != package2)
        self.assertTrue(package1 != package3)
        self.assertFalse(package1 == package3)

    def test_repr(self):
        # Given
        version = EnpkgVersion.from_string("1.3.0-1")
        metadata = PackageMetadata("nose-1.3.0-1.egg", "nose", version, [],
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
        self.assertEqual(metadata.version, EnpkgVersion.from_string("1.3.0-1"))
        self.assertEqual(metadata.dependencies, frozenset())
        self.assertEqual(metadata.packages, [])

    def test_casing(self):
        # Given
        version = EnpkgVersion.from_string("10.3-1")

        # When
        metadata = PackageMetadata("MKL-10.3-1.egg", "mkl", version, [],
                                   "2.7")
        # Then
        self.assertEqual(metadata.name, "mkl")
        self.assertEqual(metadata._egg_name, "MKL")


class TestRepositoryPackage(unittest.TestCase):
    def setUp(self):
        self.repository_info = BroodRepositoryInfo("https://acme.com",
                                                   "enthought/free")

    def test_eq(self):
        # Given
        V = EnpkgVersion.from_string
        md5 = "a" * 32
        package1 = RemotePackageMetadata("nose-1.3.0-1.egg", "nose",
                                             V("1.3.0-1"), [], "2.7", 1,
                                             md5, 0.0, "free", True,
                                             self.repository_info)
        package2 = RemotePackageMetadata("nose-1.3.0-1.egg", "nose",
                                             V("1.3.0-1"), [], "2.7", 1,
                                             md5, 0.0, "free", True,
                                             self.repository_info)
        package3 = RemotePackageMetadata("nose-1.3.0-1.egg", "nose",
                                             V("1.3.0-1"), [], "2.7", 1,
                                             "b" * 32, 0.0, "free", True,
                                             self.repository_info)

        # Then
        self.assertTrue(package1 == package2)
        self.assertTrue(hash(package1) == hash(package2))
        self.assertFalse(package1 != package2)
        self.assertTrue(package1 != package3)
        self.assertFalse(package1 == package3)

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
        version = EnpkgVersion.from_string("1.3.0-1")
        metadata = RemotePackageMetadata("nose-1.3.0-1.egg", "nose",
                                             version, [], "2.7", 1, md5,
                                             0.0, "free", True, "")

        # When/Then
        self.assertEqual(metadata.s3index_data, r_s3index_data)

    def test_from_egg(self):
        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")
        repository_info = FSRepositoryInfo(path_to_uri(os.path.dirname(path)))

        # When
        metadata = RemotePackageMetadata.from_egg(path, repository_info)

        # Then
        self.assertEqual(metadata.name, "nose")
        self.assertEqual(metadata.version, EnpkgVersion.from_string("1.3.0-1"))
        self.assertEqual(metadata.source_url, path_to_uri(path))

    def test_repr(self):
        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")
        r_repr = ("RemotePackageMetadata('nose-1.3.0-1', "
                  "key='nose-1.3.0-1.egg', available=True, product=None, "
                  "repository_info='{0}')".format(self.repository_info))

        # When
        metadata = RemotePackageMetadata.from_egg(path,
                                                      self.repository_info)

        # Then
        self.assertEqual(repr(metadata), r_repr)


class TestInstalledPackage(unittest.TestCase):
    def test_eq(self):
        # Given
        V = EnpkgVersion.from_string
        package1 = InstalledPackageMetadata("nose-1.3.0-1.egg", "nose",
                                            V("1.3.0-1"), [], "2.7",
                                            0.0, "loc1")
        package2 = InstalledPackageMetadata("nose-1.3.0-1.egg", "nose",
                                            V("1.3.0-1"), [], "2.7",
                                            0.0, "loc1")
        package3 = InstalledPackageMetadata("nose-1.3.0-1.egg", "nose",
                                            V("1.3.0-1"), [], "2.7",
                                            0.0, "loc2")

        # Then
        self.assertTrue(package1 == package2)
        self.assertTrue(hash(package1) == hash(package2))
        self.assertFalse(package1 != package2)
        self.assertTrue(package1 != package3)
        self.assertFalse(package1 == package3)

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
        self.assertEqual(metadata.dependencies, frozenset())

    def test_from_old_meta_dir(self):
        # Given
        json_dict = {
            "build": 1,
            "hook": False,
            "key": "appinst-2.1.2-1.egg",
            "name": "appinst",
            "version": "2.1.2"
        }

        # When
        metadata = InstalledPackageMetadata.from_installed_meta_dict(json_dict)

        # Then
        self.assertEqual(metadata.key, "appinst-2.1.2-1.egg")
        self.assertEqual(metadata.python, PY_VER)
        self.assertEqual(metadata.dependencies, frozenset())
        self.assertEqual(metadata.ctime, time.ctime(0.0))
