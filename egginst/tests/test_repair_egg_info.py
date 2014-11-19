import os
import shutil

from egginst._compat import assertCountEqual
from egginst.main import EggInst, setuptools_egg_info_dir
from egginst.repair_broken_egg_info import EggInfoDirFixer, repair
from egginst.testing_utils import slow
from egginst.tests.common import (DUMMY_EGG, DUMMY_EGG_WITH_ENTRY_POINTS,
                                  DUMMY_EGG_WITH_APPINST)
from egginst.tests.common import tempfile
from egginst.utils import compute_md5
from egginst.vendor.six.moves import unittest


class TestEggInfoDirFixer(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def _install_egg(self, egg_path):
        installer = EggInst(egg_path, prefix=self.prefix)
        installer.install()

    def _install_egg_empty_egg_info_dir(self, egg_path):
        installer = EggInst(egg_path, prefix=self.prefix)
        installer.install()

        egg_info_dir = os.path.join(installer.site_packages,
                                    setuptools_egg_info_dir(egg_path))
        shutil.rmtree(egg_info_dir)
        os.makedirs(egg_info_dir)

    def _install_egg_file_egg_info_dir(self, egg_path):
        installer = EggInst(egg_path, prefix=self.prefix)
        installer.install()

        egg_info_dir = os.path.join(installer.site_packages,
                                    setuptools_egg_info_dir(egg_path))
        shutil.rmtree(egg_info_dir)
        with open(egg_info_dir, "w") as fp:
            fp.write("")

    def _egg_info_path(self, egg):
        fixer = EggInfoDirFixer(egg, prefix=self.prefix)
        return fixer.egg_info_dir

    @slow
    def test_needs_repair_non_broken(self):
        """
        Ensure we detect correctly non-broken .egg-info directories
        """
        # Given
        egg_path = DUMMY_EGG
        self._install_egg(egg_path)

        # When
        fixer = EggInfoDirFixer(egg_path, prefix=self.prefix)

        # Then
        self.assertFalse(fixer.needs_repair())

    @slow
    def test_needs_repair_empty_dir(self):
        """
        Ensure we detect correctly broken .egg-info directories as installed in
        enstaller == 4.6.3 on windows.
        """
        # Given
        egg_path = DUMMY_EGG
        self._install_egg_empty_egg_info_dir(egg_path)

        # When
        fixer = EggInfoDirFixer(egg_path, prefix=self.prefix)

        # Then
        self.assertTrue(fixer.needs_repair())

    @slow
    def test_needs_repair_file_hack(self):
        """
        Ensure we detect correctly broken .egg-info files as installed in
        enstaller < 4.6.3.
        """
        # Given
        egg_path = DUMMY_EGG
        self._install_egg_file_egg_info_dir(egg_path)

        # When
        fixer = EggInfoDirFixer(egg_path, prefix=self.prefix)

        # Then
        self.assertTrue(fixer.needs_repair())

    @slow
    def test_repair_empty_dir(self):
        # Given
        egg_path = DUMMY_EGG
        self._install_egg_empty_egg_info_dir(egg_path)

        # When
        fixer = EggInfoDirFixer(egg_path, prefix=self.prefix)
        fixer.repair()

        # Then
        assertCountEqual(self, os.listdir(fixer.egg_info_dir),
                         ["PKG-INFO", "egginst.json", "_info.json"])

    @slow
    def test_repair_file(self):
        # Given
        egg_path = DUMMY_EGG
        self._install_egg_file_egg_info_dir(egg_path)

        # When
        fixer = EggInfoDirFixer(egg_path, prefix=self.prefix)
        old_egg_info_file_md5 = compute_md5(fixer.egg_info_dir)
        fixer.repair()

        # Then
        assertCountEqual(self, os.listdir(fixer.egg_info_dir),
                         ["PKG-INFO", "egginst.json", "_info.json"])
        self.assertEqual(compute_md5(os.path.join(fixer.egg_info_dir, "PKG-INFO")),
                         old_egg_info_file_md5)

    @slow
    def test_repair(self):
        # Given
        broken_as_file_egg = DUMMY_EGG
        self._install_egg_file_egg_info_dir(broken_as_file_egg)

        broken_as_empty_dir = DUMMY_EGG_WITH_ENTRY_POINTS
        self._install_egg_empty_egg_info_dir(broken_as_empty_dir)

        non_broken_egg = DUMMY_EGG_WITH_APPINST
        self._install_egg(non_broken_egg)

        # When
        repair(self.prefix, False)

        # Then
        assertCountEqual(self, os.listdir(self._egg_info_path(broken_as_file_egg)),
                         ["PKG-INFO", "egginst.json", "_info.json"])
        assertCountEqual(self, os.listdir(self._egg_info_path(broken_as_empty_dir)),
                         ["entry_points.txt", "PKG-INFO", "egginst.json",
                          "_info.json"])
        assertCountEqual(self, os.listdir(self._egg_info_path(non_broken_egg)),
                         ["PKG-INFO"])

    @slow
    def test_repair_dry_run(self):
        # Given
        broken_as_file_egg = DUMMY_EGG
        self._install_egg_file_egg_info_dir(broken_as_file_egg)

        broken_as_empty_dir = DUMMY_EGG_WITH_ENTRY_POINTS
        self._install_egg_empty_egg_info_dir(broken_as_empty_dir)

        non_broken_egg = DUMMY_EGG_WITH_APPINST
        self._install_egg(non_broken_egg)

        # When
        repair(self.prefix, True)

        # Then
        self.assertTrue(os.path.isfile(self._egg_info_path(broken_as_file_egg)))
        assertCountEqual(self,
                         os.listdir(self._egg_info_path(broken_as_empty_dir)),
                         [])
        assertCountEqual(self, os.listdir(self._egg_info_path(non_broken_egg)),
                         ["PKG-INFO"])
