import os
import sys

from egginst.main import EggInst
from egginst.vendor.six.moves import unittest

from .common import mkdtemp, SUPPORT_SYMLINK

DUMMY_EGG_WITH_PROXY_SOFTLINK = os.path.join(os.path.dirname(__file__), "data",
                                             "dummy_with_proxy_softlink-1.0.0-1.egg")


class TestLinks(unittest.TestCase):
    @unittest.skipIf(not SUPPORT_SYMLINK or sys.platform == "win32",
                     "this platform does not support symlink or proxy softlink")
    def test_simple(self):
        r_link = "libfoo.so"
        r_source = "libfoo.so.0.0.0"

        with mkdtemp() as d:
            egginst = EggInst(DUMMY_EGG_WITH_PROXY_SOFTLINK, d)
            egginst.install()

            link = os.path.join(d, "lib", r_link)
            source = os.path.join(d, "lib", r_source)
            self.assertTrue(os.path.exists(link))
            self.assertTrue(os.path.exists(source))
            self.assertTrue(os.path.islink(link))
            self.assertEqual(os.readlink(link), os.path.basename(source))
