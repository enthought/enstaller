import operator
import os.path

from egginst._compat import assertCountEqual
from egginst.main import EggInst
from egginst.utils import compute_md5
from egginst.testing_utils import slow
from egginst.tests.common import _EGGINST_COMMON_DATA, DUMMY_EGG, create_venv, mkdtemp
from egginst.vendor.six.moves import unittest

from enstaller.compat import path_to_uri
from enstaller.config import Configuration, STORE_KIND_BROOD
from enstaller.errors import NoSuchPackage
from enstaller.session import Session
from enstaller.versions.enpkg import EnpkgVersion

from enstaller.package import PackageMetadata, RemotePackageMetadata
from enstaller.repository import Repository
from enstaller.repository_info import BroodRepositoryInfo, FSRepositoryInfo
from enstaller.solver import Requirement
from enstaller.tests.common import (SIMPLE_INDEX,
                                    dummy_installed_package_factory,
                                    mock_brood_repository_indices)


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
            package = RemotePackageMetadata.from_egg(path)
            self.repository.add_package(package)

    @mock_brood_repository_indices({}, ["enthought/free"])
    def test_from_repository_info_empty(self):
        # Given
        repository_info = BroodRepositoryInfo("https://api.enthought.com",
                                              "enthought/free")
        config = Configuration(use_webservice=False,
                               auth=("nono", "password"))
        config._store_kind = STORE_KIND_BROOD

        session = Session.authenticated_from_configuration(config)

        # When
        repository = Repository.from_repository_info(session, repository_info)

        # Then
        self.assertEqual(len(repository), 0)

    @mock_brood_repository_indices(SIMPLE_INDEX, ["enthought/free"])
    def test_from_repository_info_nonempty(self):
        # Given
        repository_info = BroodRepositoryInfo("https://api.enthought.com",
                                              "enthought/free")
        config = Configuration(use_webservice=False,
                               auth=("nono", "password"))
        config._store_kind = STORE_KIND_BROOD

        session = Session.authenticated_from_configuration(config)

        # When
        repository = Repository.from_repository_info(session, repository_info)

        # Then
        self.assertEqual(len(repository), 1)
        self.assertEqual(len(repository.find_packages("nose")), 1)

    def test_ctor(self):
        # When
        repository = Repository()

        # Then
        self.assertEqual(len(repository), 0)

        # Given
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
        paths = (os.path.join(_EGGINST_COMMON_DATA, egg) for egg in eggs)
        packages = [RemotePackageMetadata.from_egg(path) for path in paths]

        # When
        repository = Repository(packages)

        # Then
        self.assertEqual(len(repository), len(eggs))

    def test_find_package(self):
        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")

        # When
        metadata = self.repository.find_package("nose", "1.3.0-1")

        # Then
        self.assertEqual(metadata.key, "nose-1.3.0-1.egg")

        self.assertEqual(metadata.name, "nose")
        self.assertEqual(metadata.version, EnpkgVersion.from_string("1.3.0-1"))

        self.assertEqual(metadata.dependencies, frozenset())
        self.assertEqual(metadata.python, "2.7")

        self.assertEqual(metadata.available, True)
        self.assertEqual(metadata.repository_info,
                         FSRepositoryInfo(path_to_uri(_EGGINST_COMMON_DATA)))

        self.assertEqual(metadata.size, os.path.getsize(path))
        self.assertEqual(metadata.md5, compute_md5(path))

        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-2.egg")

        # When
        metadata = self.repository.find_package("nose", "1.3.0-2")

        # Then
        self.assertEqual(metadata.key, "nose-1.3.0-2.egg")

        self.assertEqual(metadata.name, "nose")
        self.assertEqual(metadata.version, EnpkgVersion.from_string("1.3.0-2"))

    def test_find_unavailable_package(self):
        # Given/When/Then
        with self.assertRaises(NoSuchPackage):
            self.repository.find_package("nono", "1.4.0-1")

    def test_find_packages(self):
        V = EnpkgVersion.from_string
        # Given/When
        metadata = list(self.repository.find_packages("nose"))
        metadata = sorted(metadata, key=operator.attrgetter("version"))

        # Then
        self.assertEqual(len(metadata), 3)

        self.assertEqual(metadata[0].version, V("1.2.1-1"))
        self.assertEqual(metadata[1].version, V("1.3.0-1"))
        self.assertEqual(metadata[2].version, V("1.3.0-2"))

    def test_find_packages_with_version(self):
        # Given/When
        metadata = list(self.repository.find_packages("nose", "1.3.0-1"))

        # Then
        self.assertEqual(len(metadata), 1)

        self.assertEqual(metadata[0].version,
                         EnpkgVersion.from_string("1.3.0-1"))

    def test_has_package(self):
        # Given
        version = EnpkgVersion.from_string("1.3.0-1")
        available_package = PackageMetadata("nose-1.3.0-1.egg", "nose",
                                            version, [], "2.7")

        version = EnpkgVersion.from_string("1.4.0-1")
        unavailable_package = PackageMetadata("nose-1.4.0-1.egg", "nose",
                                              version, [], "2.7")

        # When/Then
        self.assertTrue(self.repository.has_package(available_package))
        self.assertFalse(self.repository.has_package(unavailable_package))

    def test_iter_most_recent_packages(self):
        # Given
        eggs = ["nose-1.3.0-1.egg", "nose-1.2.1-1.egg"]
        repository = Repository()
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RemotePackageMetadata.from_egg(path)
            repository.add_package(package)

        # When
        metadata = list(repository.iter_most_recent_packages())

        # Then
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0].version,
                         EnpkgVersion.from_string("1.3.0-1"))

    def test_iter_protocol(self):
        # Given
        eggs = ["nose-1.3.0-1.egg", "nose-1.2.1-1.egg"]
        repository = Repository()
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RemotePackageMetadata.from_egg(path)
            repository.add_package(package)

        # When
        metadata = list(iter(repository))

        # Then
        self.assertEqual(len(metadata), 2)
        self.assertEqual(set(m.version for m in metadata),
                         set([EnpkgVersion.from_string("1.2.1-1"),
                              EnpkgVersion.from_string("1.3.0-1")]))

    def test_iter_packages(self):
        # Given
        eggs = ["nose-1.3.0-1.egg", "nose-1.2.1-1.egg"]
        repository = Repository()
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RemotePackageMetadata.from_egg(path)
            repository.add_package(package)

        # When
        metadata = list(repository.iter_packages())

        # Then
        self.assertEqual(len(metadata), 2)
        self.assertEqual(set(m.version for m in metadata),
                         set([EnpkgVersion.from_string("1.2.1-1"),
                              EnpkgVersion.from_string("1.3.0-1")]))

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
        with self.assertRaises(NoSuchPackage):
            repository.delete_package(to_remove)

    def test_delete_simple(self):
        # Given
        eggs = ["flake8-2.0.0-2.egg", "nose-1.3.0-1.egg", "nose-1.2.1-1.egg"]
        repository = Repository()
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RemotePackageMetadata.from_egg(path)
            repository.add_package(package)

        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")
        to_remove = PackageMetadata.from_egg(path)

        # When
        repository.delete_package(to_remove)

        # Then
        assertCountEqual(self, [p.key for p in repository.iter_packages()],
                         ["flake8-2.0.0-2.egg", "nose-1.2.1-1.egg"])

    def test_find_package_from_requirement_name_only(self):
        # Given
        requirement = Requirement.from_anything("nose")

        # When
        package = self.repository.find_package_from_requirement(requirement)

        # Then
        self.assertEqual(package.full_version, "1.3.0-2")

    def test_find_package_from_requirement_name_and_version(self):
        # Given
        requirement = Requirement.from_anything("nose 1.3.0")

        # When
        package = self.repository.find_package_from_requirement(requirement)

        # Then
        self.assertEqual(package.full_version, "1.3.0-2")

        # Given
        requirement = Requirement.from_anything("nose 1.2.1")

        # When
        package = self.repository.find_package_from_requirement(requirement)

        # Then
        self.assertEqual(package.full_version, "1.2.1-1")

    def test_find_package_from_requirement_missing(self):
        # Given
        requirement_strings = ["fubar", "nose 1.3.1"]

        # When
        for requirement_string in requirement_strings:
            requirement = Requirement.from_anything(requirement_string)
            with self.assertRaises(NoSuchPackage):
                self.repository.find_package_from_requirement(requirement)

    def test_find_package_from_requirement_all(self):
        # Given
        requirement = Requirement.from_anything("nose 1.3.0-1")

        # When
        package = self.repository.find_package_from_requirement(requirement)

        # Then
        self.assertEqual(package.full_version, "1.3.0-1")

        # Given
        requirement = Requirement.from_anything("nose 1.2.1-1")

        # When
        package = self.repository.find_package_from_requirement(requirement)

        # Then
        self.assertEqual(package.full_version, "1.2.1-1")

    def test_sorted_insertion(self):
        # Given
        eggs = ["nose-1.3.0-1.egg", "nose-1.2.1-1.egg"]
        repository = Repository()

        # When
        for egg in eggs:
            path = os.path.join(_EGGINST_COMMON_DATA, egg)
            package = RemotePackageMetadata.from_egg(path)
            repository.add_package(package)

        # Then
        self.assertEqual([m.version
                          for m in repository._name_to_packages["nose"]],
                         [EnpkgVersion.from_string("1.2.1-1"),
                          EnpkgVersion.from_string("1.3.0-1")])


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
        assertCountEqual(self, packages, entries)

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
        self.assertEqual([p.version for p in packages],
                         [EnpkgVersion.from_string(v)
                          for v in ("1.6.1-1", "1.7.1-1", "1.8.0-2")])

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
        assertCountEqual(self, [p.version for p in packages],
                         [EnpkgVersion.from_string(v)
                          for v in ("1.6.1-1", "1.8k-2")])
