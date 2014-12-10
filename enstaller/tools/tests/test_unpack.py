import os.path
import shutil
import tempfile

import mock

from egginst.vendor.six.moves import unittest
from egginst.tests.common import NOSE_1_2_1, NOSE_1_3_0

from ..unpack import main


class TestMain(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    @mock.patch("enstaller.tools.unpack.extract_egg")
    def test_simple(self, extract_egg):
        # Given
        argv = [self.prefix, NOSE_1_3_0]

        # When
        main(argv)

        # Then
        extract_egg.assert_called_with(NOSE_1_3_0, self.prefix)

    @mock.patch("enstaller.tools.unpack.extract_egg")
    def test_multiple_eggs(self, extract_egg):
        # Given
        argv = [self.prefix, NOSE_1_2_1, NOSE_1_3_0]
        r_calls = [
            mock.call(NOSE_1_2_1, self.prefix),
            mock.call(NOSE_1_3_0, self.prefix),
        ]

        # When
        main(argv)

        # Then
        extract_egg.assert_has_calls(r_calls)

    def test_real(self):
        # Given
        argv = [self.prefix, NOSE_1_2_1]
        r_man = os.path.join(self.prefix, "share", "man", "man1",
                             "nosetests.1")

        # When
        main(argv)

        # Then
        self.assertTrue(os.path.exists(r_man))
