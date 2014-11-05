import json
import os.path
import shutil
import tempfile

from egginst.vendor.six.moves import unittest
from egginst.tests.common import _EGGINST_COMMON_DATA

from enstaller.egg_meta import info_from_egg, update_index


class TestInfoFromEgg(unittest.TestCase):
    def test_simple(self):
        # Given
        r_info = {
            'arch': 'amd64',
            'build': 1,
            'name': 'nose',
            'osdist': None,
            'packages': [],
            'platform': 'darwin',
            'python': '2.7',
            'type': 'egg',
            'version': '1.3.0'
        }
        path = os.path.join(_EGGINST_COMMON_DATA, "nose-1.3.0-1.egg")

        # When
        info = info_from_egg(path)

        # Then
        self.assertEqual(info, r_info)


class TestUpdateIndex(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_simple(self):
        # Given
        for egg in ["nose-1.3.0-1.egg", "nose-1.3.0-2.egg"]:
            shutil.copy(os.path.join(_EGGINST_COMMON_DATA, egg), self.tempdir)
        index_path = os.path.join(self.tempdir, "index.json")

        # When
        update_index(self.tempdir)

        # Then
        with open(index_path) as fp:
            data = json.load(fp)
            print(data)
