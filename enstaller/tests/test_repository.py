import itertools
import operator
import os.path
import sys

import mock
import six

from egginst._compat import assertCountEqual
from egginst.main import EggInst
from egginst.utils import compute_md5
from egginst.testing_utils import slow
from egginst.tests.common import _EGGINST_COMMON_DATA, DUMMY_EGG, create_venv, mkdtemp

from enstaller.compat import path_to_uri
from enstaller.config import Configuration, STORE_KIND_BROOD
from enstaller.errors import NoSuchPackage
from enstaller.session import Session
from enstaller.utils import RUNNING_PYTHON
from enstaller.versions import EnpkgVersion

from enstaller.package import PackageMetadata, RemotePackageMetadata
from enstaller.repository import _RequirementNormalizer, Repository
from enstaller.repository_info import BroodRepositoryInfo, FSRepositoryInfo
from enstaller.solver import Requirement
from enstaller.tests.common import (SIMPLE_INDEX, WarningTestMixin,
                                    dummy_installed_package_factory,
                                    mock_brood_repository_indices)

if sys.version_info[0] == 2:
    import unittest2 as unittest
else:
    import unittest


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
    def test_from_repository_infos_empty(self):
        # Given
        repository_info = BroodRepositoryInfo("https://api.enthought.com",
                                              "enthought/free")
        config = Configuration(use_webservice=False,
                               auth=("nono", "password"))
        config._store_kind = STORE_KIND_BROOD

        session = Session.authenticated_from_configuration(config)

        # When
        repository = Repository.from_repository_infos(
            session, (repository_info,)
        )

        # Then
        self.assertEqual(len(repository), 0)

    @mock_brood_repository_indices(
        SIMPLE_INDEX, ["enthought/free", "enthought/commercial"]
    )
    def test_from_repository_infos_nonempty(self):
        # Given
        repository_infos = (
            BroodRepositoryInfo("https://api.enthought.com", "enthought/free"),
            BroodRepositoryInfo(
                "https://api.enthought.com", "enthought/commercial"
            ),
        )
        config = Configuration(use_webservice=False,
                               auth=("nono", "password"))
        config._store_kind = STORE_KIND_BROOD

        session = Session.authenticated_from_configuration(config)

        # When
        repository = Repository.from_repository_infos(session, repository_infos)

        # Then
        self.assertEqual(len(repository), 2)
        self.assertEqual(len(repository.find_packages("nose")), 2)

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
        python = RUNNING_PYTHON
        version = EnpkgVersion.from_string("1.3.0-1")
        available_package = PackageMetadata("nose-1.3.0-1.egg", "nose",
                                            version, [], python)

        version = EnpkgVersion.from_string("1.4.0-1")
        unavailable_package = PackageMetadata("nose-1.4.0-1.egg", "nose",
                                              version, [], python)

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

    def test_from_prefix_normalization(self):
        # Given
        r_installed_metadata = {
            "PyYAML-3.11-1.egg": {
                "arch": "amd64",
                "build": 1,
                "key": "PyYAML-3.11-1.egg",
                "md5": "4d1df29c87bb101747b5a774b720f543",
                "name": "pyyaml",
                "osdist": "RedHat_5",
                "packages": [
                    "libYAML 0.1.4"
                ],
                "platform": "linux2",
                "product": "free",
                "python": "2.7",
                "size": 183069,
                "type": "egg",
                "version": "3.11"
            },
            "libYAML-0.1.4-1.egg": {
                "arch": "amd64",
                "build": 1,
                "key": "libYAML-0.1.4-1.egg",
                "md5": "3679f8a4f6c852ed65a3b9809bbecd13",
                "name": "libyaml",
                "osdist": "RedHat_5",
                "packages": [],
                "platform": "linux2",
                "python": None,
                "version": "0.1.4"
            }
        }

        def info_from_metadir(meta_dir):
            if meta_dir == os.path.join("dummy_prefix", "EGG-INFO", "libyaml"):
                return r_installed_metadata["libYAML-0.1.4-1.egg"]
            elif meta_dir == os.path.join("dummy_prefix", "EGG-INFO", "pyyaml"):
                return r_installed_metadata["PyYAML-3.11-1.egg"]
            else:
                return None

        def _valid_meta_dir_iterator(prefixes):
            for prefix in prefixes:
                egg_info_root = os.path.join(prefix, "EGG-INFO")
                for info in six.itervalues(r_installed_metadata):
                    yield (
                        prefix, egg_info_root,
                        os.path.join(egg_info_root, info["name"])
                    )

        # When
        with mock.patch(
            "enstaller.repository._valid_meta_dir_iterator",
            _valid_meta_dir_iterator
        ):
            with mock.patch(
                "enstaller.repository.info_from_metadir",
                info_from_metadir
            ):
                repository = Repository._from_prefixes(["dummy_prefix"])

        # Then
        packages = repository.find_packages("pyyaml")
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].name, "pyyaml")
        self.assertEqual(packages[0].dependencies, frozenset(["libyaml 0.1.4",]))

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
        requirement = Requirement.from_legacy_requirement_string("nose")

        # When
        package = self.repository.find_package_from_requirement(requirement)

        # Then
        self.assertEqual(package.full_version, "1.3.0-2")

    def test_find_package_from_requirement_name_and_version(self):
        # Given
        requirement = Requirement.from_legacy_requirement_string("nose 1.3.0")

        # When
        package = self.repository.find_package_from_requirement(requirement)

        # Then
        self.assertEqual(package.full_version, "1.3.0-2")

        # Given
        requirement = Requirement.from_legacy_requirement_string("nose 1.2.1")

        # When
        package = self.repository.find_package_from_requirement(requirement)

        # Then
        self.assertEqual(package.full_version, "1.2.1-1")

    def test_find_package_from_requirement_missing(self):
        # Given
        requirement_strings = ["fubar", "nose 1.3.1"]

        # When
        for requirement_string in requirement_strings:
            requirement = Requirement.from_legacy_requirement_string(requirement_string)
            with self.assertRaises(NoSuchPackage):
                self.repository.find_package_from_requirement(requirement)

    def test_find_package_from_requirement_all(self):
        # Given
        requirement = Requirement.from_legacy_requirement_string("nose 1.3.0-1")

        # When
        package = self.repository.find_package_from_requirement(requirement)

        # Then
        self.assertEqual(package.full_version, "1.3.0-1")

        # Given
        requirement = Requirement.from_legacy_requirement_string("nose 1.2.1-1")

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

    def test_update(self):
        # Given
        def repository_factory_from_egg(filenames):
            repository = Repository()
            for filename in filenames:
                path = os.path.join(_EGGINST_COMMON_DATA, filename)
                package = RemotePackageMetadata.from_egg(path)
                repository.add_package(package)
            return repository

        egg_set1 = (
            "dummy-1.0.1-1.egg",
            "dummy_with_appinst-1.0.0-1.egg",
            "dummy_with_entry_points-1.0.0-1.egg",
            "dummy_with_proxy-1.3.40-3.egg",
        )

        egg_set2 = (
            "dummy_with_proxy_scripts-1.0.0-1.egg",
            "dummy_with_proxy_softlink-1.0.0-1.egg",
            "nose-1.2.1-1.egg",
            "nose-1.3.0-1.egg",
            "nose-1.3.0-2.egg",
        )

        repository = Repository()
        repository1 = repository_factory_from_egg(egg_set1)
        repository2 = repository_factory_from_egg(egg_set2)

        # When
        repository.update(repository1)

        # Then
        assertCountEqual(self, iter(repository), iter(repository1))

        # When
        repository.update(repository2)

        # Then
        assertCountEqual(
            self, iter(repository),
            itertools.chain(iter(repository1), iter(repository2))
        )


class TestRepositoryMisc(WarningTestMixin, unittest.TestCase):
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

    def test_find_packages_sorting(self):
        # Given
        entries = [
            dummy_installed_package_factory("numpy", "1.6.1", 1),
            dummy_installed_package_factory("numpy", "1.8.0", 2),
            dummy_installed_package_factory("numpy", "1.7.1", 1),
        ]
        repository = Repository()
        for entry in entries:
            repository.add_package(entry)

        r_versions = [
            EnpkgVersion.from_string(v)
            for v in ("1.6.1-1", "1.7.1-1", "1.8.0-2")
        ]

        # When
        packages = repository.find_packages("numpy")

        # Then
        self.assertEqual(len(packages), 3)
        self.assertEqual([p.version for p in packages], r_versions)

        with self.assertWarns(DeprecationWarning):
            deprecated_packages = repository.find_sorted_packages("numpy")
        self.assertEqual([p.version for p in deprecated_packages], r_versions)

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
        packages = repository.find_packages("numpy")

        # Then
        self.assertEqual(len(packages), 2)
        assertCountEqual(self, [p.version for p in packages],
                         [EnpkgVersion.from_string(v)
                          for v in ("1.6.1-1", "1.8k-2")])

        with self.assertWarns(DeprecationWarning):
            deprecated_packages = repository.find_sorted_packages("numpy")
        self.assertEqual(deprecated_packages, packages)


class Test_RequirementNormalizer(unittest.TestCase):
    def test_simple(self):
        # Given
        r_normalized_numpy = {
            "name": "numpy",
            "packages": ["mkl 10.3-1"],
        }

        index = {
            "MKL-10.3-1.egg": {
                "name": "mkl",
                "packages": [],
            },
            "numpy-1.9.2-1.egg": {
                "name": "numpy",
                "packages": ["MKL 10.3-1"],
            },
        }

        # When
        normalizer = _RequirementNormalizer(index)
        normalized_numpy = normalizer(
            "numpy-1.9.2-1.egg", index["numpy-1.9.2-1.egg"]
        )

        # Then
        self.assertEqual(normalized_numpy, r_normalized_numpy)

    def test_preserve_casing(self):
        # AFAIK, name is always all lower-case, but we may want to support
        # casing in names latter on (especially for interoperability w/ pypi)

        # Given
        r_normalized_dummy = {
            "name": "dummy",
            "packages": ["Cython 0.23.4"],
        }

        index = {
            "Cython-0.23.4-1.egg": {
                "name": "Cython",
                "packages": [],
            },
            "dummy-1.0.0-1.egg": {
                "name": "dummy",
                "packages": ["Cython 0.23.4"],
            },
        }

        # When
        normalizer = _RequirementNormalizer(index)
        normalized_dummy = normalizer(
            "dummy-1.0.0-1.egg", index["dummy-1.0.0-1.egg"]
        )

        # Then
        self.assertEqual(normalized_dummy, r_normalized_dummy)
