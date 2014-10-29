import contextlib
import os.path
import shutil
import tempfile
import textwrap

import mock

from okonomiyaki.errors import OkonomiyakiError
from okonomiyaki.platforms.legacy import LegacyEPDPlatform

from egginst._compat import TestCase
from egginst._zipfile import ZipFile
from egginst.eggmeta import info_from_z
from egginst.tests.common import DUMMY_EGG, STANDARD_EGG, NOSE_1_2_1

from enstaller.errors import EnstallerException
from enstaller.tools.repack import main, repack


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

    def test_repack_default_platform_unsupported(self):
        # Given
        source = os.path.join(self.prefix, "nose-1.2.1-py2.7.egg")
        shutil.copy(STANDARD_EGG, source)

        target = os.path.join(self.prefix, "nose-1.2.1-1.egg")

        # When/Then
        mocked = "enstaller.tools.repack.LegacyEPDPlatform." \
                 "from_running_system"
        platform = LegacyEPDPlatform.from_epd_platform_string("rh5-32")
        with mock.patch(mocked, side_effect=OkonomiyakiError()):
            with self.assertRaises(EnstallerException):
                repack(source, 1)

        # Then
        self.assertFalse(os.path.exists(target))

    def test_repack_default_platform(self):
        # Given
        source = os.path.join(self.prefix, "nose-1.2.1-py2.7.egg")
        shutil.copy(STANDARD_EGG, source)

        target = os.path.join(self.prefix, "nose-1.2.1-1.egg")

        # When
        mocked = "enstaller.tools.repack.LegacyEPDPlatform." \
                 "from_running_system"
        platform = LegacyEPDPlatform.from_epd_platform_string("rh5-32")
        with mock.patch(mocked, return_value=platform):
            repack(source, 1)

        # Then
        self.assertTrue(os.path.exists(target))
        with ZipFile(target) as zp:
            spec = info_from_z(zp)
        self.assertEqual(spec["arch"], "x86")

    def test_unsupported_format(self):
        # Given
        source = os.path.join(self.prefix, "nose-1.2.1-1.egg")
        shutil.copy(STANDARD_EGG, source)

        # When/Then
        with self.assertRaises(EnstallerException):
            repack(source, 1, "rh5-64")

    def test_refuse_inplace(self):
        # Given
        target = os.path.join(self.prefix, "dummy-1.0.1-1.egg")
        source = target

        shutil.copy(DUMMY_EGG, source)

        # When/Then
        with self.assertRaises(EnstallerException):
            repack(source, 1, "rh5-64")

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
        with ZipFile(target) as zp:
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
        with ZipFile(target) as zp:
            data = zp.read("EGG-INFO/foo.txt").decode("utf8")
        self.assertEqual(data, "babar")

    def test_endist_unsupported_key(self):
        # Given
        source = os.path.join(self.prefix, os.path.basename(NOSE_1_2_1))
        shutil.copy(NOSE_1_2_1, source)

        target = os.path.join(self.prefix, "nose-1.2.1-2.egg")
        endist = os.path.join(self.prefix, "endist.dat")
        with open(endist, "w") as fp:
            data = "app_icon_file = 'fubar.ico'"
            fp.write(data)

        # When/Then
        with chdir(self.prefix):
            with self.assertRaises(NotImplementedError):
                repack(source, 2, "rh5-64")


class TestRepackMain(TestCase):
    def test_help(self):
        # Given
        args = ["-h"]

        # When
        with self.assertRaises(SystemExit) as e:
            with mock.patch("enstaller.tools.repack.repack") as repack:
                main(args)

        # Then
        self.assertFalse(repack.called)
        self.assertEqual(e.exception.code, 0)

    def test_usual_args(self):
        # Given
        args = ["nose-1.3.0-py2.7.egg", "-b", "3", "-a", "win-32"]

        # When
        with mock.patch("enstaller.tools.repack.repack") as repack:
            main(args)

        # Then
        self.assertTrue(repack.called)
        self.assertTrue(repack.called_with("nose-1.3.0-py2.7.egg", "-b",
                                           "3", "-a", "win-32"))
