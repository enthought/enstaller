import os.path
import posixpath

import enstaller.plat

from egginst.tests.common import DUMMY_EGG
from egginst.vendor.six.moves import unittest

from enstaller.repository_info import (BroodRepositoryInfo,
                                       CanopyRepositoryInfo,
                                       FSRepositoryInfo,
                                       OldstyleRepositoryInfo)
from enstaller.repository import RemotePackageMetadata
from enstaller.utils import path_to_uri


class TestLegacyRepositoryInfo(unittest.TestCase):
    def test_eq_and_hashing(self):
        # Given
        store_url = "https://acme.com"

        # When
        info1 = OldstyleRepositoryInfo(store_url)
        info2 = OldstyleRepositoryInfo(store_url)

        # Then
        self.assertEqual(info1, info2)
        self.assertFalse(info1 != info2)
        self.assertEqual(hash(info1), hash(info2))

        # When
        info3 = OldstyleRepositoryInfo("https://bunny.com")

        # Then
        self.assertNotEqual(info1, info3)
        self.assertTrue(info1 != info3)

    def test_simple(self):
        # Given
        store_url = "https://acme.com/foo/eggs/platform/"
        path = DUMMY_EGG

        r_index_url = "https://acme.com/foo/eggs/platform/index.json"
        r_package_url = "https://acme.com/foo/eggs/platform/{0}".format(os.path.basename(path))

        # When
        info = OldstyleRepositoryInfo(store_url)
        package = RemotePackageMetadata.from_egg(path)

        # Then
        self.assertEqual(info._base_url, store_url)
        self.assertEqual(info.index_url, r_index_url)
        self.assertEqual(info.name, "/foo/eggs/platform/")
        self.assertEqual(info._package_url(package), r_package_url)


class TestCanopyRepositoryInfo(unittest.TestCase):
    def test_simple(self):
        # Given
        platform = "haiku-x86"
        store_url = "https://acme.com"
        r_name = "canopy+https://acme.com"

        # When
        info = CanopyRepositoryInfo(store_url, use_pypi=True,
                                    platform=platform)

        # Then
        self.assertEqual(info.name, r_name)
        self.assertEqual(info._base_url, store_url + "/eggs/" + platform + "/")

    def test_eq_and_hashing(self):
        # Given
        store_url = "https://acme.com/eggs/platform"

        # When
        info1 = CanopyRepositoryInfo(store_url, use_pypi=True)
        info2 = CanopyRepositoryInfo(store_url, use_pypi=True)
        info3 = OldstyleRepositoryInfo(store_url)

        # Then
        self.assertEqual(info1, info2)
        self.assertFalse(info1 != info2)
        self.assertFalse(info1 == info3)
        self.assertEqual(hash(info1), hash(info2))

        # When
        info3 = CanopyRepositoryInfo(store_url, use_pypi=False)

        # Then
        self.assertNotEqual(info1, info3)
        self.assertTrue(info1 != info3)

    def test_pypi(self):
        # Given
        store_url = "https://acme.com"
        path = DUMMY_EGG

        r_index_url = ("https://acme.com/eggs/{0}/index.json?pypi=true".
                       format(enstaller.plat.custom_plat))
        r_package_url = ("https://acme.com/eggs/{0}/{1}".
                         format(enstaller.plat.custom_plat,
                                os.path.basename(path)))

        # When
        info = CanopyRepositoryInfo(store_url, use_pypi=True)
        package = RemotePackageMetadata.from_egg(path)

        # Then
        self.assertEqual(info.index_url, r_index_url)
        self.assertEqual(info._package_url(package), r_package_url)

        # Given
        r_index_url = ("https://acme.com/eggs/{0}/index.json?pypi=false".
                       format(enstaller.plat.custom_plat))

        # When
        info = CanopyRepositoryInfo(store_url, use_pypi=False)

        # Then
        self.assertEqual(info.index_url, r_index_url)


class TestBroodRepositoryInfo(unittest.TestCase):
    def test_eq_and_hashing(self):
        # Given
        store_url = "https://acme.com"
        name = "enthought/free"

        # When
        info1 = BroodRepositoryInfo(store_url, name)
        info2 = BroodRepositoryInfo(store_url, name)

        # Then
        self.assertEqual(info1, info2)
        self.assertFalse(info1 != info2)
        self.assertEqual(hash(info1), hash(info2))

        # When
        info3 = BroodRepositoryInfo(store_url, "enthought/commercial")

        # Then
        self.assertNotEqual(info1, info3)
        self.assertTrue(info1 != info3)

    def test_simple(self):
        # Given
        store_url = "https://acme.com"
        name = "enthought/free"
        path = DUMMY_EGG

        r_index_url = ("https://acme.com/repo/{0}/{1}/index.json"
                       .format(name, enstaller.plat.custom_plat))
        r_package_url = ("https://acme.com/repo/{0}/{1}/{2}".
                         format(name, enstaller.plat.custom_plat,
                                os.path.basename(path)))
        r__base_url = ("https://acme.com/repo/{0}/{1}/"
                       .format(name, enstaller.plat.custom_plat))

        # When
        info = BroodRepositoryInfo(store_url, name)
        package = RemotePackageMetadata.from_egg(path)

        # Then
        self.assertEqual(info.index_url, r_index_url)
        self.assertEqual(info.name, name)
        self.assertEqual(info._package_url(package), r_package_url)
        self.assertEqual(info._base_url, r__base_url)


class TestFSRepositoryInfo(unittest.TestCase):
    def test_eq_and_hashing(self):
        # Given
        store_url = path_to_uri(os.path.dirname(DUMMY_EGG))

        # When
        info1 = FSRepositoryInfo(store_url)
        info2 = FSRepositoryInfo(store_url)

        # Then
        self.assertEqual(info1, info2)
        self.assertFalse(info1 != info2)
        self.assertEqual(hash(info1), hash(info2))

        # When
        info3 = FSRepositoryInfo("file://fubar")

        # Then
        self.assertNotEqual(info1, info3)
        self.assertTrue(info1 != info3)

    def test_simple(self):
        # Given
        path = DUMMY_EGG
        store_url = path_to_uri(os.path.dirname(path))

        r__base_url = path_to_uri(os.path.dirname(path))
        r_index_url = posixpath.join(store_url, "index.json")
        r_package_url = path_to_uri(path)

        # When
        info = FSRepositoryInfo(store_url)
        package = RemotePackageMetadata.from_egg(path)

        # Then
        self.assertEqual(info.index_url, r_index_url)
        self.assertEqual(info.name, store_url)
        self.assertEqual(info._base_url, r__base_url)
        self.assertEqual(info._package_url(package), r_package_url)
