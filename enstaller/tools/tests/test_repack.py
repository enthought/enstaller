import contextlib
import os.path
import shutil
import tempfile
import textwrap
import zipfile

from egginst._compat import TestCase
from egginst.eggmeta import info_from_z
from egginst.tests.common import STANDARD_EGG, NOSE_1_2_1

from enstaller.tools.repack import repack


@contextlib.contextmanager
def chdir(d):
    old = os.getcwd()
    os.chdir(d)
    yield old
    os.chdir(old)

class TestRepack(TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_simple_setuptools_egg(self):
        # Given
        source = os.path.join(self.prefix, os.path.basename(STANDARD_EGG))
        shutil.copy(STANDARD_EGG, source)

        target = os.path.join(self.prefix, "Jinja2-2.6-1.egg")

        # When
        repack(source, 1, "rh5-64")

        # Then
        self.assertTrue(os.path.exists(target))

    def test_simple_enthought_egg(self):
        # Given
        source = os.path.join(self.prefix, os.path.basename(NOSE_1_2_1))
        shutil.copy(NOSE_1_2_1, source)

        target = os.path.join(self.prefix, "nose-1.2.1-2.egg")

        # When
        repack(source, 2, "rh5-64")

        # Then
        self.assertTrue(os.path.exists(target))

    def test_endist_metadata_simple(self):
        # Given
        source = os.path.join(self.prefix, os.path.basename(NOSE_1_2_1))
        shutil.copy(NOSE_1_2_1, source)

        target = os.path.join(self.prefix, "babar-1.2.1-2.egg")
        endist = os.path.join(self.prefix, "endist.dat")
        with open(endist, "w") as fp:
            data = textwrap.dedent("""\
            packages = ["foo"]

            name = "babar"
            """)
            fp.write(data)

        # When
        with chdir(self.prefix):
            repack(source, 2, "rh5-64")

        # Then
        self.assertTrue(os.path.exists(target))
        with zipfile.ZipFile(target) as zp:
            info = info_from_z(zp)
        self.assertItemsEqual(info["packages"], ["foo"])
        self.assertItemsEqual(info["name"], "babar")

    def test_endist_add_files_simple(self):
        # Given
        source = os.path.join(self.prefix, os.path.basename(NOSE_1_2_1))
        shutil.copy(NOSE_1_2_1, source)

        target = os.path.join(self.prefix, "nose-1.2.1-2.egg")
        endist = os.path.join(self.prefix, "endist.dat")
        with open(endist, "w") as fp:
            data = textwrap.dedent("""\
            packages = ["foo"]

            add_files = [(".", "foo*", "EGG-INFO")]
            """)
            fp.write(data)
        fubar = os.path.join(self.prefix, "foo.txt")
        with open(fubar, "w") as fp:
            fp.write("babar")

        # When
        with chdir(self.prefix):
            repack(source, 2, "rh5-64")

        # Then
        self.assertTrue(os.path.exists(target))
        with zipfile.ZipFile(target) as zp:
            data = zp.read("EGG-INFO/foo.txt")
        self.assertEqual(data, "babar")
