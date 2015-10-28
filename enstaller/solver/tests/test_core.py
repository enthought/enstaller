from __future__ import absolute_import

import os.path
import shutil
import tempfile
import sys

from egginst.main import EGG_INFO, EggInst
from egginst.tests.common import DUMMY_EGG, NOSE_1_2_1, NOSE_1_3_0
from egginst.utils import makedirs


from enstaller.egg_meta import split_eggname
from enstaller.errors import (
    MissingDependency, NotInstalledPackage, NoPackageFound
)
from enstaller.package import InstalledPackageMetadata
from enstaller.repository import Repository

from ..core import ForceMode, Solver
from ..request import Request
from ..requirement import Requirement

from enstaller.tests.common import (dummy_installed_package_factory,
                                    dummy_repository_package_factory,
                                    repository_factory)

if sys.version_info[0] == 2:
    import unittest2 as unittest
else:
    import unittest


class TestSolverNoDependencies(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_install_simple(self):
        numpy_1_8_0 = dummy_repository_package_factory("numpy", "1.8.0", 2)
        entries = [
            dummy_repository_package_factory("numpy", "1.6.1", 1),
            numpy_1_8_0,
            dummy_repository_package_factory("numpy", "1.7.1", 2),
        ]

        r_actions = [('install', numpy_1_8_0)]

        repository = repository_factory(entries)
        installed_repository = Repository._from_prefixes([self.prefix])
        solver = Solver(repository, installed_repository)

        request = Request()
        request.install(Requirement("numpy"))
        actions = solver.resolve(request)

        self.assertEqual(actions, r_actions)

    def test_install_no_egg_entry(self):
        # Given
        entries = [
            dummy_repository_package_factory("numpy", "1.6.1", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
        ]

        repository = repository_factory(entries)
        installed_repository = Repository._from_prefixes([self.prefix])
        solver = Solver(repository, installed_repository)

        request = Request()
        request.install(Requirement("scipy"))

        # When/Then
        with self.assertRaises(NoPackageFound):
            solver.resolve(request)

    def test_install_missing_dependency(self):
        # Given
        entries = [
            dummy_repository_package_factory("numpy", "1.8.0", 2,
                                             dependencies=["MKL 10.3"]),
        ]

        repository = repository_factory(entries)
        installed_repository = Repository._from_prefixes([self.prefix])
        solver = Solver(repository, installed_repository)

        request = Request()
        request.install(Requirement("numpy"))

        # When/Then
        with self.assertRaises(MissingDependency):
            solver.resolve(request)

    def test_remove_actions(self):
        # Given
        repository = Repository()

        for egg in [DUMMY_EGG]:
            egginst = EggInst(egg, self.prefix)
            egginst.install()

        installed_repository = Repository._from_prefixes([self.prefix])

        solver = Solver(repository, installed_repository)

        request = Request()
        request.remove(Requirement("dummy"))

        # When
        actions = solver.resolve(request)

        # Then
        self.assertEqual(
            actions,
            [("remove", installed_repository.find_packages("dummy")[0])]
        )

    def test_remove_non_existing(self):
        # Given
        entries = [
            dummy_repository_package_factory("numpy", "1.6.1", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
        ]

        repository = repository_factory(entries)
        solver = Solver(repository, Repository._from_prefixes([self.prefix]))

        request = Request()
        request.remove(Requirement("numpy"))

        # When/Then
        with self.assertRaises(NotInstalledPackage):
            solver.resolve(request)

    def test_chained_override_update(self):
        """ Test update to package with latest version in lower prefix
        but an older version in primary prefix.
        """
        # Given
        l0_egg = NOSE_1_3_0
        l1_egg = NOSE_1_2_1

        nose = dummy_repository_package_factory(
            *split_eggname(os.path.basename(l0_egg))
        )

        repository = repository_factory([nose])

        l0 = os.path.join(self.prefix, 'l0')
        l1 = os.path.join(self.prefix, 'l1')
        makedirs(l0)
        makedirs(l1)

        l1_egg_meta_dir = os.path.join(l1, EGG_INFO, "nose")

        # Install latest version in l0
        EggInst(l0_egg, l0).install()

        # Install older version in l1
        EggInst(l1_egg, l1).install()

        installed_nose = InstalledPackageMetadata.from_meta_dir(
            l1_egg_meta_dir, prefix=l1
        )
        expected_actions = [('remove', installed_nose), ('install', nose)]

        installed_repository = Repository._from_prefixes([l1])
        solver = Solver(repository, installed_repository)

        request = Request()
        request.install(Requirement("nose"))

        # When
        actions = solver.resolve(request)

        # Then
        self.assertListEqual(actions, expected_actions)


class TestSolverDependencies(unittest.TestCase):
    def test_simple(self):
        # Given
        entries = [
            dummy_repository_package_factory("MKL", "10.3", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2,
                                             dependencies=["MKL 10.3"]),
        ]

        repository = repository_factory(entries)
        installed_repository = Repository()

        expected_actions = [
            ('install', entries[0]), ('install', entries[1])
        ]

        request = Request()
        request.install(Requirement("numpy"))

        # When
        solver = Solver(repository, installed_repository)
        actions = solver.resolve(request)

        # Then
        self.assertListEqual(actions, expected_actions)

    def test_simple_installed(self):
        # Given
        remote_numpy = dummy_repository_package_factory(
            "numpy", "1.8.0", 2, dependencies=["MKL 10.3"]
        )
        entries = [
            remote_numpy,
            dummy_repository_package_factory("MKL", "10.3", 1),
        ]

        repository = repository_factory(entries)
        installed_repository = Repository()
        installed_repository.add_package(
            dummy_installed_package_factory("MKL", "10.3", 1)
        )

        expected_actions = [('install', remote_numpy)]

        # When
        request = Request()
        request.install(Requirement("numpy"))

        solver = Solver(repository, installed_repository)
        actions = solver.resolve(request)

        # Then
        self.assertListEqual(actions, expected_actions)

    def test_simple_all_installed(self):
        # Given
        remote_mkl = dummy_repository_package_factory("MKL", "10.3", 1)
        remote_numpy = dummy_repository_package_factory(
            "numpy", "1.8.0", 2, dependencies=["MKL 10.3"]
        )
        entries = [remote_mkl, remote_numpy]

        repository = repository_factory(entries)

        installed_mkl = dummy_installed_package_factory("MKL", "10.3", 1)
        installed_numpy = dummy_installed_package_factory("numpy", "1.8.0", 2)
        installed_entries = [installed_mkl, installed_numpy]

        installed_repository = Repository()
        for package in installed_entries:
            installed_repository.add_package(package)

        # When
        request = Request()
        request.install(Requirement("numpy"))

        solver = Solver(repository, installed_repository)
        actions = solver.resolve(request)

        # Then
        self.assertListEqual(actions, [])

        # When
        solver = Solver(
            repository, installed_repository, force=ForceMode.MAIN_ONLY
        )
        actions = solver.resolve(request)

        # Then
        self.assertListEqual(
            actions, [("remove", installed_numpy), ("install", remote_numpy)]
        )

        # When
        solver = Solver(repository, installed_repository, force=ForceMode.ALL)
        actions = solver.resolve(request)

        # Then
        self.assertListEqual(
            actions,
            [("remove", installed_numpy), ("remove", installed_mkl),
             ("install", remote_mkl), ("install", remote_numpy)]
        )
