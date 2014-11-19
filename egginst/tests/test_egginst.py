import os
import os.path
import shutil
import sys
import tempfile

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock
import testfixtures

from egginst.main import (
    EggInst, get_installed, is_in_legacy_egg_info, main,
    should_copy_in_egg_info)
from egginst.testing_utils import assert_same_fs
from egginst.utils import makedirs, zip_write_symlink
from egginst._zipfile import ZipFile

from egginst import eggmeta

from .common import (DUMMY_EGG, DUMMY_EGG_WITH_APPINST,
                     DUMMY_EGG_WITH_ENTRY_POINTS, DUMMY_EGG_METADATA_FILES,
                     LEGACY_EGG_INFO_EGG, LEGACY_EGG_INFO_EGG_METADATA_FILES,
                     NOSE_1_3_0, PYTHON_VERSION, STANDARD_EGG,
                     STANDARD_EGG_METADATA_FILES, SUPPORT_SYMLINK,
                     VTK_EGG_DEFERRED_SOFTLINK, mkdtemp)


def _create_egg_with_symlink(filename, name):
    with ZipFile(filename, "w") as fp:
        fp.writestr("EGG-INFO/usr/include/foo.h", "/* header */")
        zip_write_symlink(fp, "EGG-INFO/usr/HEADERS", "include")


def _create_dummy_enstaller_egg(prefix):
    path = os.path.join(prefix, "enstaller-4.8.0-1.egg")
    with ZipFile(path, "w") as fp:
        # We write a dummy file as empty zip files are not properly handled by
        # zipfile in python 2.6
        fp.writestr("EGG-INFO/dummy", "")
    return path


class TestEggInst(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        makedirs(self.base_dir)
        self.prefix = os.path.join(self.base_dir, "prefix")

    def tearDown(self):
        shutil.rmtree(self.base_dir)

    @unittest.skipIf(not SUPPORT_SYMLINK,
                     "this platform does not support symlink")
    def test_symlink(self):
        """Test installing an egg with softlink in it."""
        # Given
        if sys.platform == "win32":
            incdir = os.path.join(self.prefix, "EGG-INFO", "foo", "usr",
                                  "include")
            header = os.path.join(incdir, "foo.h")
            link = os.path.join(self.prefix, "EGG-INFO", "foo", "usr",
                                "HEADERS")
        else:
            incdir = os.path.join(self.prefix, "include")
            header = os.path.join(incdir, "foo.h")
            link = os.path.join(self.prefix, "HEADERS")

        egg_filename = os.path.join(self.base_dir, "foo-1.0.egg")
        _create_egg_with_symlink(egg_filename, "foo")
        # When
        installer = EggInst(egg_filename, prefix=self.prefix)
        installer.install()

        # Then
        self.assertTrue(os.path.exists(header))
        self.assertTrue(os.path.exists(link))
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.readlink(link), "include")
        self.assertTrue(os.path.exists(os.path.join(link, "foo.h")))

    @unittest.skipIf(not SUPPORT_SYMLINK or sys.platform == "win32",
                     "this platform does not support symlink")
    def test_softlink_with_broken_entry(self):
        # Given
        path = VTK_EGG_DEFERRED_SOFTLINK

        # When
        installer = EggInst(path, prefix=self.prefix)
        installer.install()

    def test_enstaller_no_placeholder_hack(self):
        # Given
        path = _create_dummy_enstaller_egg(self.base_dir)

        # When
        with mock.patch("egginst.main.object_code.apply_placeholder_hack") \
                as m:
            installer = EggInst(path, prefix=self.prefix)
            installer.install()

        # Then
        self.assertFalse(m.called)


class TestEggInstMain(unittest.TestCase):
    def test_print_version(self):
        # XXX: this is lousy test: we'd like to at least ensure we're printing
        # the correct version, but capturing the stdout is a bit tricky. Once
        # we replace print by proper logging, we should be able to do better.
        main(["--version"])

    def test_list(self):
        # XXX: this is lousy test: we'd like to at least ensure we're printing
        # the correct packages, but capturing the stdout is a bit tricky. Once
        # we replace print by proper logging, we should be able to do better.
        main(["--list"])

    def test_install_simple(self):
        with mkdtemp() as d:
            main([DUMMY_EGG, "--prefix={0}".format(d)])

            self.assertTrue(os.path.basename(DUMMY_EGG) in list(get_installed(d)))

            main(["-r", DUMMY_EGG, "--prefix={0}".format(d)])

            self.assertFalse(os.path.basename(DUMMY_EGG) in list(get_installed(d)))

    def test_get_installed(self):
        r_installed_eggs = sorted([
            os.path.basename(DUMMY_EGG),
            os.path.basename(DUMMY_EGG_WITH_ENTRY_POINTS),
        ])

        with mkdtemp() as d:
            egginst = EggInst(DUMMY_EGG, d)
            egginst.install()

            egginst = EggInst(DUMMY_EGG_WITH_ENTRY_POINTS, d)
            egginst.install()

            installed_eggs = list(get_installed(d))
            self.assertEqual(installed_eggs, r_installed_eggs)


class Test_EggInstRemove(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_simple_(self):
        # Given
        remover = EggInst(DUMMY_EGG, self.prefix)

        # When
        with testfixtures.LogCapture() as logger:
            remover.remove()

        # Then
        logger.check(
            ('egginst.main', 'ERROR',
             "Error: Can't find meta data for: 'dummy'")
        )


class TestEggInstInstall(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()

        if sys.platform == "win32":
            self.bindir = os.path.join(self.base_dir, "Scripts")
            self.site_packages = os.path.join(self.base_dir, "lib", "site-packages")
        else:
            self.bindir = os.path.join(self.base_dir, "bin")
            self.site_packages = os.path.join(self.base_dir, "lib", "python" + PYTHON_VERSION, "site-packages")

        self.meta_dir = os.path.join(self.base_dir, "EGG-INFO")

    def tearDown(self):
        shutil.rmtree(self.base_dir)

    def test_simple(self):
        egginst = EggInst(DUMMY_EGG, self.base_dir)

        egginst.install()
        self.assertTrue(os.path.exists(os.path.join(self.site_packages, "dummy.py")))

        egginst.remove()
        self.assertFalse(os.path.exists(os.path.join(self.site_packages, "dummy.py")))

    def test_non_existing_removal(self):
        """
        Regression test for #208
        """
        # Given
        non_existing_package = "nono_le_petit_robot"

        # When/Then
        main(["--remove", non_existing_package])

    def test_entry_points(self):
        """
        Test we install console entry points correctly.
        """
        py_script = os.path.join(self.site_packages, "dummy.py")
        if sys.platform == "win32":
            wrapper_script = os.path.join(self.bindir, "dummy.exe")
        else:
            wrapper_script = os.path.join(self.bindir, "dummy")

        egginst = EggInst(DUMMY_EGG_WITH_ENTRY_POINTS, self.base_dir)

        egginst.install()
        self.assertTrue(os.path.exists(py_script))
        self.assertTrue(os.path.exists(wrapper_script))

        egginst.remove()
        self.assertFalse(os.path.exists(py_script))
        self.assertFalse(os.path.exists(wrapper_script))

    def test_appinst(self):
        """
        Test we install appinst bits correctly.
        """
        egg_path = DUMMY_EGG_WITH_APPINST
        appinst_path = os.path.join(self.meta_dir, "dummy_with_appinst", eggmeta.APPINST_PATH)

        egginst = EggInst(egg_path, self.base_dir)

        with mock.patch("appinst.install_from_dat", autospec=True) as m:
            egginst.install()
            m.assert_called_with(appinst_path, self.base_dir)

        with mock.patch("appinst.uninstall_from_dat", autospec=True) as m:
            egginst.remove()
            m.assert_called_with(appinst_path, self.base_dir)

    def test_old_appinst(self):
        """
        Test that we still work with old (<= 2.1.1) appinst, where
        [un]install_from_dat only takes one argument (no prefix).
        """
        egg_path = DUMMY_EGG_WITH_APPINST
        appinst_path = os.path.join(self.meta_dir, "dummy_with_appinst", eggmeta.APPINST_PATH)

        egginst = EggInst(egg_path, self.base_dir)

        def mocked_old_install_from_dat(x):
            pass

        def mocked_old_uninstall_from_dat(x):
            pass

        # XXX: we use autospec to enforce function taking exactly one argument,
        # otherwise the proper TypeError exception is not raised when calling
        # it with two arguments, which is how old vs new appinst is detected.
        with mock.patch("appinst.install_from_dat", autospec=mocked_old_install_from_dat) as m:
            egginst.install()
            m.assert_called_with(appinst_path)

        with mock.patch("appinst.uninstall_from_dat", autospec=mocked_old_uninstall_from_dat) as m:
            egginst.remove()
            m.assert_called_with(appinst_path)

    def test_without_appinst(self):
        """
        Test egginst does not crash when appinst is not available and we try
        installing eggs using appinst
        """
        egg_path = DUMMY_EGG_WITH_APPINST

        egginst = EggInst(egg_path, self.base_dir)

        with mock.patch("egginst.main.appinst", None):
            egginst.install()
            egginst.remove()

    def test_appinst_failed(self):
        """
        Test egginst does not crash when appinst is not available and we try
        installing eggs using appinst
        """
        egg_path = DUMMY_EGG_WITH_APPINST

        egginst = EggInst(egg_path, self.base_dir)

        with mock.patch("egginst.main.appinst.install_from_dat", side_effect=ValueError):
            egginst.install()

        with mock.patch("egginst.main.appinst.uninstall_from_dat", side_effect=ValueError):
            egginst.remove()


class TestEggInfoInstall(unittest.TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()

        if sys.platform == "win32":
            self.bindir = os.path.join(self.base_dir, "Scripts")
            self.site_packages = os.path.join(self.base_dir, "lib", "site-packages")
        else:
            self.bindir = os.path.join(self.base_dir, "bin")
            self.site_packages = os.path.join(self.base_dir, "lib", "python" + PYTHON_VERSION, "site-packages")

        self.meta_dir = os.path.join(self.base_dir, "EGG-INFO")

    def tearDown(self):
        shutil.rmtree(self.base_dir)

    def test_is_custom_egg(self):
        r_output = [
            (STANDARD_EGG, False),
            (DUMMY_EGG_WITH_APPINST, True),
            (DUMMY_EGG, True),
        ]

        for egg, expected in r_output:
            self.assertEqual(eggmeta.is_custom_egg(egg), expected)

    def test_standard_egg(self):
        custom_egg_info_base = os.path.join(self.base_dir, "EGG-INFO", "jinja2")
        egg_info_base = os.path.join(self.site_packages,
                                     "Jinja2-2.6-py2.7.egg-info")

        egg = STANDARD_EGG

        egginst = EggInst(egg, self.base_dir)
        egginst.install()

        # Check for files installed in $prefix/EGG-INFO
        for f in STANDARD_EGG_METADATA_FILES:
            path = os.path.join(custom_egg_info_base, f)
            self.assertTrue(os.path.exists(path))

        # Check for files installed in $site-packages/$package_egg_info-INFO
        for f in STANDARD_EGG_METADATA_FILES:
            path = os.path.join(egg_info_base, f)
            self.assertTrue(os.path.exists(path))

    def test_standard_egg_remove(self):
        egg = STANDARD_EGG

        with assert_same_fs(self, self.base_dir):
            egginst = EggInst(egg, self.base_dir)
            egginst.install()

            egginst.remove()

    def test_simple_custom_egg(self):
        custom_egg_info_base = os.path.join(self.base_dir, "EGG-INFO", "dummy")
        egg_info_base = os.path.join(self.site_packages,
                                     "dummy-{0}.egg-info".
                                     format("1.0.1-1"))
        egg = DUMMY_EGG

        egginst = EggInst(egg, self.base_dir)
        egginst.install()

        # Check for files installed in $prefix/EGG-INFO
        for f in DUMMY_EGG_METADATA_FILES:
            path = os.path.join(custom_egg_info_base, f)
            self.assertTrue(os.path.exists(path))

        # Check for files installed in $site-packages/$package_egg_info-INFO
        path = os.path.join(egg_info_base, "PKG-INFO")
        self.assertTrue(os.path.exists(path))

        path = os.path.join(egg_info_base, "spec/depend")
        self.assertFalse(os.path.exists(path))

        path = os.path.join(egg_info_base, "spec/summary")
        self.assertFalse(os.path.exists(path))

    def test_simple_custom_egg_remove(self):
        egg = DUMMY_EGG

        with assert_same_fs(self, self.base_dir):
            egginst = EggInst(egg, self.base_dir)
            egginst.install()
            egginst.remove()

    def test_custom_egg_with_usr_files(self):
        custom_egg_info_base = os.path.join(self.base_dir, "EGG-INFO", "nose")
        egg_info_base = os.path.join(self.site_packages,
                                     "nose-{0}.egg-info".
                                     format("1.3.0-1"))
        egg = NOSE_1_3_0

        egginst = EggInst(egg, self.base_dir)
        egginst.install()

        # Check for files installed in $prefix/EGG-INFO
        for f in DUMMY_EGG_METADATA_FILES:
            path = os.path.join(custom_egg_info_base, f)
            self.assertTrue(os.path.exists(path))

        # Check for files installed in $site-packages/$package_egg_info-INFO
        path = os.path.join(egg_info_base, "PKG-INFO")
        self.assertTrue(os.path.exists(path))

        path = os.path.join(egg_info_base, "spec/depend")
        self.assertFalse(os.path.exists(path))

        path = os.path.join(egg_info_base, "spec/summary")
        self.assertFalse(os.path.exists(path))

        path = os.path.join(egg_info_base, "usr/share/man/man1/nosetests.1")
        self.assertFalse(os.path.exists(path))

    def test_custom_egg_with_usr_files_remove(self):
        egg = NOSE_1_3_0

        with assert_same_fs(self, self.base_dir):
            egginst = EggInst(egg, self.base_dir)
            egginst.install()
            egginst.remove()

    def test_custom_egg_legacy_egg_info(self):
        custom_egg_info_base = os.path.join(self.base_dir, "EGG-INFO", "flake8")
        egg_info_base = os.path.join(self.site_packages,
                                     "flake8-2.0.0-2.egg-info")
        legacy_egg_info_base = os.path.join(self.site_packages, "flake8.egg-info")

        custom_metadata = ("PKG-INFO.bak", "requires.txt", "spec/depend",
                           "spec/summary")

        egg = LEGACY_EGG_INFO_EGG

        egginst = EggInst(egg, self.base_dir)
        egginst.install()

        # Check for files installed in $prefix/EGG-INFO
        for f in custom_metadata:
            path = os.path.join(custom_egg_info_base, f)
            self.assertTrue(os.path.exists(path))

        # Check for files installed in $site-packages/$package_egg_info-INFO
        for f in LEGACY_EGG_INFO_EGG_METADATA_FILES:
            path = os.path.join(egg_info_base, f)
            self.assertTrue(os.path.exists(path))

        for f in LEGACY_EGG_INFO_EGG_METADATA_FILES:
            path = os.path.join(legacy_egg_info_base, f)
            self.assertFalse(os.path.exists(path))

    def test_custom_egg_legacy_egg_info_remove(self):
        egg = LEGACY_EGG_INFO_EGG

        with assert_same_fs(self, self.base_dir):
            egginst = EggInst(egg, self.base_dir)
            egginst.install()
            egginst.remove()


class TestMisc(unittest.TestCase):
    def test_should_copy_custom_egg(self):
        # Given
        is_custom_egg = True

        # Then
        self.assertFalse(should_copy_in_egg_info("EGG-INFO/spec/depend",
                                                 is_custom_egg))
        self.assertTrue(should_copy_in_egg_info("EGG-INFO/SOURCES.txt",
                                                is_custom_egg))

    def test_should_copy_standard_egg(self):
        # Given
        is_custom_egg = False

        # Then
        self.assertTrue(should_copy_in_egg_info("EGG-INFO/spec/depend",
                                                is_custom_egg))
        self.assertTrue(should_copy_in_egg_info("EGG-INFO/SOURCES.txt",
                                                is_custom_egg))

    def test_is_in_legacy_info_custom_eggs(self):
        # Given
        is_custom_egg = True

        # Then
        self.assertFalse(is_in_legacy_egg_info("EGG-INFO/spec/depend",
                                               is_custom_egg))
        self.assertFalse(is_in_legacy_egg_info("dummy/__init__.py",
                                               is_custom_egg))
        self.assertTrue(is_in_legacy_egg_info("dummy.egg-info/__init__.py",
                                              is_custom_egg))
        self.assertTrue(is_in_legacy_egg_info("dummy.egg-info", is_custom_egg))
        self.assertTrue(is_in_legacy_egg_info("dummy-1.0.0.egg-info",
                                              is_custom_egg))

    def test_is_in_legacy_info_standard_eggs(self):
        # Given
        is_custom_egg = False

        # Then
        self.assertFalse(is_in_legacy_egg_info("EGG-INFO/spec/depend",
                                               is_custom_egg))
        self.assertFalse(is_in_legacy_egg_info("dummy/__init__.py",
                                               is_custom_egg))
        self.assertFalse(is_in_legacy_egg_info("dummy.egg-info/__init__.py",
                                               is_custom_egg))
        self.assertFalse(is_in_legacy_egg_info("dummy.egg-info", is_custom_egg))
        self.assertFalse(is_in_legacy_egg_info("dummy-1.0.0.egg-info",
                                               is_custom_egg))
