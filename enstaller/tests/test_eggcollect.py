import os.path
import tempfile
import textwrap

from egginst.vendor.six.moves import unittest
from enstaller.eggcollect import info_from_metadir


class TestInfoFromMetaDir(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        self.tempdir = tempfile.mkdtemp()

    def test_simple(self):
        # Given
        data = textwrap.dedent("""{
            "arch": "amd64",
            "build": 1,
            "ctime": "Thu Apr 24 15:41:24 2014",
            "hook": false,
            "key": "VTK-5.10.1-1.egg",
            "name": "vtk",
            "osdist": "RedHat_5",
            "packages": [],
            "platform": "linux2",
            "python": "2.7",
            "type": "egg",
            "version": "5.10.1"
        }""")
        r_info = {
            "arch": "amd64",
            "build": 1,
            "ctime": "Thu Apr 24 15:41:24 2014",
            "hook": False,
            "installed": True,
            "key": "VTK-5.10.1-1.egg",
            "meta_dir": self.tempdir,
            "name": "vtk",
            "osdist": "RedHat_5",
            "packages": [],
            "platform": "linux2",
            "python": "2.7",
            "type": "egg",
            "version": "5.10.1"
        }
        info_json = os.path.join(self.tempdir, "_info.json")
        with open(info_json, "w") as fp:
            fp.write(data)

        # When
        info = info_from_metadir(self.tempdir)

        # Then
        self.assertEqual(info, r_info)
