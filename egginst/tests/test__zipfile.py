import os.path

from egginst.utils import compute_md5, ensure_dir
from egginst.tests.common import (NOSE_1_3_0, SUPPORT_SYMLINK,
                                  VTK_EGG_DEFERRED_SOFTLINK, ZIP_WITH_SOFTLINK,
                                  mkdtemp)
from egginst.vendor.six import BytesIO
from egginst.vendor.six.moves import unittest

from egginst._compat import assertCountEqual
from egginst._zipfile import ZipFile


def list_files(top):
    paths = []
    for root, dirs, files in os.walk(top):
        for f in files:
            paths.append(os.path.join(os.path.relpath(root, top), f))
    return paths


def create_broken_symlink(link):
    ensure_dir(link)
    d = os.path.dirname(link)
    os.symlink(os.path.join(d, "nono_le_petit_robot"), link)


class TestZipFile(unittest.TestCase):
    def test_simple(self):
        # Given
        path = NOSE_1_3_0
        r_paths = [
            os.path.join("EGG-INFO", "entry_points.txt"),
            os.path.join("EGG-INFO", "PKG-INFO"),
            os.path.join("EGG-INFO", "spec", "depend"),
            os.path.join("EGG-INFO", "spec", "summary"),
            os.path.join("EGG-INFO", "usr", "share", "man", "man1", "nosetests.1"),
        ]

        # When
        with mkdtemp() as d:
            with ZipFile(path) as zp:
                zp.extractall(d)
            paths = list_files(d)

        # Then
        assertCountEqual(self, paths, r_paths)

    def test_extract(self):
        # Given
        path = NOSE_1_3_0
        arcname = "EGG-INFO/PKG-INFO"

        # When
        with mkdtemp() as d:
            with ZipFile(path) as zp:
                zp.extract(arcname, d)
            self.assertTrue(os.path.exists(os.path.join(d, arcname)))

    def test_extract_to(self):
        # Given
        path = NOSE_1_3_0
        arcname = "EGG-INFO/PKG-INFO"

        # When
        with mkdtemp() as d:
            with ZipFile(path) as zp:
                zp.extract_to(arcname, "FOO", d)
                extracted_data = zp.read(arcname)
            self.assertTrue(os.path.exists(os.path.join(d, "FOO")))
            self.assertEqual(compute_md5(os.path.join(d, "FOO")),
                             compute_md5(BytesIO(extracted_data)))
            self.assertFalse(os.path.exists(os.path.join(d, "EGG-INFO",
                                                         "PKG-INFO")))

    @unittest.skipIf(not SUPPORT_SYMLINK,
                     "this platform does not support symlink")
    def test_softlink(self):
        # Given
        path = ZIP_WITH_SOFTLINK

        # When/Then
        with mkdtemp() as d:
            with ZipFile(path) as zp:
                zp.extractall(d)
            paths = list_files(d)

            assertCountEqual(self, paths, [os.path.join("lib", "foo.so.1.3"),
                                           os.path.join("lib", "foo.so")])
            self.assertTrue(os.path.islink(os.path.join(d, "lib", "foo.so")))

    @unittest.skipIf(not SUPPORT_SYMLINK,
                     "this platform does not support symlink")
    def test_softlink_with_broken_entry(self):
        self.maxDiff = None

        # Given
        path = VTK_EGG_DEFERRED_SOFTLINK
        expected_files = [
            os.path.join('EGG-INFO', 'PKG-INFO'),
            os.path.join('EGG-INFO', 'inst', 'targets.dat'),
            os.path.join('EGG-INFO', 'inst', 'files_to_install.txt'),
            os.path.join('EGG-INFO', 'usr', 'lib', 'vtk-5.10', 'libvtkViews.so.5.10.1'),
            os.path.join('EGG-INFO', 'usr', 'lib', 'vtk-5.10', 'libvtkViews.so.5.10'),
            os.path.join('EGG-INFO', 'usr', 'lib', 'vtk-5.10', 'libvtkViews.so'),
            os.path.join('EGG-INFO', 'spec', 'lib-provide'),
            os.path.join('EGG-INFO', 'spec', 'depend'),
            os.path.join('EGG-INFO', 'spec', 'lib-depend'),
            os.path.join('EGG-INFO', 'spec', 'summary'),
        ]

        with mkdtemp() as d:
            existing_link = os.path.join(d, 'EGG-INFO/usr/lib/vtk-5.10/libvtkViews.so')
            create_broken_symlink(existing_link)

            # When
            with ZipFile(path) as zp:
                zp.extractall(d)
            files = list_files(d)

            # Then
            assertCountEqual(self, files, expected_files)
            path = os.path.join(d, "EGG-INFO/usr/lib/vtk-5.10/libvtkViews.so")
            self.assertTrue(os.path.islink(path))
