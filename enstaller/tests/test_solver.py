import os.path
import shutil
import sys
import tempfile

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from egginst.main import EggInst
from egginst.tests.common import DUMMY_EGG, NOSE_1_2_1, NOSE_1_3_0
from egginst.utils import makedirs


from enstaller.egg_meta import split_eggname
from enstaller.errors import EnpkgError, NoPackageFound
from enstaller.repository import Repository
from enstaller.solver import Solver

from .common import dummy_repository_package_factory, repository_factory


class TestSolver(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_install_simple(self):
        entries = [
            dummy_repository_package_factory("numpy", "1.6.1", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
            dummy_repository_package_factory("numpy", "1.7.1", 2),
        ]

        r_actions = [
            ('fetch_0', 'numpy-1.8.0-2.egg'),
            ('install', 'numpy-1.8.0-2.egg')
        ]

        repository = repository_factory(entries)
        installed_repository = Repository._from_prefixes([self.tempdir])
        solver = Solver(repository, installed_repository)

        actions = solver.install_actions("numpy")

        self.assertEqual(actions, r_actions)

    def test_install_no_egg_entry(self):
        entries = [
            dummy_repository_package_factory("numpy", "1.6.1", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
        ]

        repository = repository_factory(entries)
        installed_repository = Repository._from_prefixes([self.tempdir])
        solver = Solver(repository, installed_repository)

        with self.assertRaises(NoPackageFound):
            solver.install_actions("scipy")

    def test_remove_actions(self):
        repository = Repository()

        for egg in [DUMMY_EGG]:
            egginst = EggInst(egg, self.tempdir)
            egginst.install()

        solver = Solver(repository, Repository._from_prefixes([self.tempdir]))

        actions = solver.remove_actions("dummy")
        self.assertEqual(actions, [("remove", os.path.basename(DUMMY_EGG))])

    def test_remove_non_existing(self):
        entries = [
            dummy_repository_package_factory("numpy", "1.6.1", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
        ]

        repository = repository_factory(entries)
        solver = Solver(repository, Repository._from_prefixes([self.tempdir]))

        with self.assertRaises(EnpkgError):
            solver.remove_actions("numpy")

    def test_chained_override_update(self):
        """ Test update to package with latest version in lower prefix
        but an older version in primary prefix.
        """
        l0_egg = NOSE_1_3_0
        l1_egg = NOSE_1_2_1

        expected_actions = [
            ('fetch_0', os.path.basename(l0_egg)),
            ('remove', os.path.basename(l1_egg)),
            ('install', os.path.basename(l0_egg)),
        ]

        entries = [
            dummy_repository_package_factory(*split_eggname(os.path.basename(l0_egg))),
        ]

        repository = repository_factory(entries)

        l0 = os.path.join(self.tempdir, 'l0')
        l1 = os.path.join(self.tempdir, 'l1')
        makedirs(l0)
        makedirs(l1)

        # Install latest version in l0
        EggInst(l0_egg, l0).install()
        # Install older version in l1
        EggInst(l1_egg, l1).install()

        repository = repository_factory(entries)
        installed_repository = Repository._from_prefixes([l1])
        solver = Solver(repository, installed_repository)

        actions = solver.install_actions("nose")
        self.assertListEqual(actions, expected_actions)
