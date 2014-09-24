import os.path
import shutil
import tempfile

from egginst._compat import TestCase
from egginst.tests.common import STANDARD_EGG, NOSE_1_2_1

from enstaller.tools.repack import repack


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
