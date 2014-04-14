import sys
import textwrap

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from cStringIO import StringIO

from egginst.utils import parse_assignments
from enstaller.errors import InvalidFormat


class TestParseAssignments(unittest.TestCase):
    def test_parse_simple(self):
        r_data = {"IndexedRepos": ["http://acme.com/{SUBDIR}"],
                  "webservice_entry_point": "http://acme.com/eggs/{PLATFORM}/"}

        s = textwrap.dedent("""\
        IndexedRepos = [
            "http://acme.com/{SUBDIR}",
        ]
        webservice_entry_point = "http://acme.com/eggs/{PLATFORM}/"
        """)

        data = parse_assignments(StringIO(s))
        self.assertEqual(data, r_data)

    def test_parse_simple_invalid_file(self):
        with self.assertRaises(InvalidFormat):
            parse_assignments(StringIO("EPD_auth = 1 + 2"))

        with self.assertRaises(InvalidFormat):
            parse_assignments(StringIO("1 + 2"))
