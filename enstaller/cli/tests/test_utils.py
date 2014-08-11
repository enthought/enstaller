import shutil
import tempfile
import unittest


from enstaller.cli.utils import disp_store_info, name_egg


class TestMisc(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_disp_store_info(self):
        info = {"store_location": "https://api.enthought.com/eggs/osx-64/"}
        self.assertEqual(disp_store_info(info), "api osx-64")

        info = {"store_location": "https://api.enthought.com/eggs/win-32/"}
        self.assertEqual(disp_store_info(info), "api win-32")

        info = {}
        self.assertEqual(disp_store_info(info), "-")

    def test_name_egg(self):
        name = "foo-1.0.0-1.egg"
        self.assertEqual(name_egg(name), "foo")

        name = "fu_bar-1.0.0-1.egg"
        self.assertEqual(name_egg(name), "fu_bar")

        with self.assertRaises(AssertionError):
            name = "some/dir/fu_bar-1.0.0-1.egg"
            name_egg(name)
