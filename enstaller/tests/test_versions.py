import unittest

from enstaller.utils import comparable_version
from enstaller.versions import NormalizedVersion

class TestVersion(unittest.TestCase):
    def test_single_number(self):
        """Test that we handle versions such as '214' correctly."""
        r_ver = NormalizedVersion("214.0.0")

        ver_string = "214"
        self.assertEqual(comparable_version(ver_string), r_ver)

    def test_dev_tag_without_number(self):
        """Test that we handle buggy '1.0.0.dev' as if it were '1.0.0.dev1'."""
        r_ver = NormalizedVersion("1.0.0.dev1")

        ver_string = "1.0.0.dev"
        self.assertEqual(comparable_version(ver_string), r_ver)
