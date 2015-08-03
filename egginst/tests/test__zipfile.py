import errno
import hashlib
import os.path
import stat

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

    @unittest.skipIf(not SUPPORT_SYMLINK,
                     "this platform does not support symlink")
    def test_existing_symlink_replacement(self):
        # Ensure that when we overwrite an existing file with extract* methods,
        # we don't fail in the case a file already exists but is a symlink to a
        # file we don't have access to.
        self.maxDiff = None

        # Given
        some_data = b"some data"
        path = ZIP_WITH_SOFTLINK
        r_files = [
            os.path.join("lib", "foo.so.1.3"), os.path.join("lib", "foo.so")
        ]
        r_link = os.path.join("lib", "foo.so")
        r_file = os.path.join("lib", "foo.so.1.3")

        with mkdtemp() as tempdir:
            with mkdtemp() as tempdir2:
                def _create_read_only_file(read_only_file):
                    with open(read_only_file, "wb") as fp:
                        fp.write(some_data)

                    mode = os.stat(read_only_file)[stat.ST_MODE]
                    os.chmod(
                        read_only_file,
                        mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH
                    )

                    try:
                        with open(read_only_file, "wb") as fp:
                            pass
                        raise RuntimeError("Creation of RO file failed")
                    except IOError as e:
                        if e.errno != errno.EACCES:
                            raise

                def _create_link_to_ro(link_to_read_only_file):
                    # Hack: we create a symlink toward a RO file to check the
                    # destination can be overwritten
                    link_to_read_only_file = os.path.join(tempdir, r_file)
                    assert not os.path.islink(link_to_read_only_file)

                    os.unlink(link_to_read_only_file)
                    os.symlink(read_only_file, link_to_read_only_file)

                read_only_file = os.path.join(tempdir2, "read_only_file")
                _create_read_only_file(read_only_file)

                # When
                with ZipFile(path) as zp:
                    zp.extractall(tempdir)

                original_file = os.path.join(tempdir, r_file)
                original_file_md5 = compute_md5(original_file)

                _create_link_to_ro(original_file)

                with ZipFile(path) as zp:
                    zp.extractall(tempdir)
                files = list_files(tempdir)

                # Then
                assertCountEqual(self, files, r_files)
                self.assertTrue(os.path.islink(os.path.join(tempdir, r_link)))
                self.assertFalse(os.path.islink(original_file))
                self.assertEqual(compute_md5(original_file), original_file_md5)
                # Making sure we did not modify the file originally linked to
                # by the overwritten symlink
                self.assertEqual(
                    compute_md5(read_only_file), hashlib.md5(some_data).hexdigest()
                )
