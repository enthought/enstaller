import unittest

from egginst.eggmeta import info_from_z, parse_rawspec
from egginst.vendor.six import BytesIO
from egginst._zipfile import ZipFile

NUMPY_1_4_0_WIN32 = """\
metadata_version = '1.1'
name = 'numpy'
version = '1.4.0'
build = 3

arch = 'x86'
platform = 'win32'
osdist = None
python = '2.6'
packages = []
"""

PIL_1_1_7_WIN32 = """\
metadata_version = '1.1'
name = 'PIL'
version = '1.1.7'
build = 3

arch = 'x86'
platform = 'win32'
osdist = None
python = '2.7'
packages = []
"""


def _create_inmemory_egg(archives):
    s = BytesIO()
    with ZipFile(s, "w") as z:
        for arcname, data in archives.items():
            z.writestr(arcname, data)
    s.seek(0)

    return s


class TestParseRawSpec(unittest.TestCase):
    def test_simple(self):
        data = NUMPY_1_4_0_WIN32

        r_metadata = {
            "name": "numpy",
            "version": "1.4.0",
            "build": 3,
            "arch": "x86",
            "platform": "win32",
            "osdist": None,
            "python": "2.6",
            "packages": []
        }
        metadata = parse_rawspec(data)

        self.assertEqual(metadata, r_metadata)


class TestInfoFromZ(unittest.TestCase):
    def test_simple(self):
        r_metadata = {
            "name": "numpy",
            "version": "1.4.0",
            "build": 3,
            "arch": "x86",
            "platform": "win32",
            "osdist": None,
            "python": "2.6",
            "packages": [],
            "type": "egg",
        }

        s = _create_inmemory_egg({"EGG-INFO/spec/depend": NUMPY_1_4_0_WIN32})
        with ZipFile(s) as z:
            metadata = info_from_z(z)
            self.assertEqual(metadata, r_metadata)

    def test_name_casing(self):
        r_metadata = {
            "name": "pil",
            "version": "1.1.7",
            "build": 3,
            "arch": "x86",
            "platform": "win32",
            "osdist": None,
            "python": "2.7",
            "packages": [],
            "type": "egg",
        }

        s = _create_inmemory_egg({"EGG-INFO/spec/depend": PIL_1_1_7_WIN32})
        with ZipFile(s) as z:
            metadata = info_from_z(z)
            self.assertEqual(metadata, r_metadata)
