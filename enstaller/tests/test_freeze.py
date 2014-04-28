import os
import os.path
import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from egginst.main import EggInst
from egginst.tests.common import _EGGINST_COMMON_DATA, DUMMY_EGG, create_venv, mkdtemp

from enstaller.freeze import get_freeze_list


class TestFreeze(unittest.TestCase):
    def test_simple(self):
        # Given
        path = os.path.join(_EGGINST_COMMON_DATA, DUMMY_EGG)
        with mkdtemp() as tempdir:
            create_venv(tempdir)
            installer = EggInst(path, prefix=tempdir)
            installer.install()

            # When
            freeze_list = get_freeze_list([tempdir])

        self.assertEqual(freeze_list, ["dummy 1.0.1-1"])
