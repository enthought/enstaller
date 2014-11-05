import os
import tempfile

from egginst.vendor.six.moves import unittest

from egginst._post_install_lib import safe_write, update_pkg_config_prefix


class TestSafeWrite(unittest.TestCase):
    def setUp(self):
        f = tempfile.NamedTemporaryFile(delete=False)
        self.filename = f.name
        f.close()

    def tearDown(self):
        os.remove(self.filename)

    def test_simple(self):
        """Test whether the file content is correctly written when using string."""
        name = self.filename
        safe_write(name, "foo")

        with open(name) as fp:
            self.assertEqual(fp.read(), "foo")

    def test_already_exists(self):
        """Test whether safe_write works when the target already exists."""
        safe_write(self.filename, "foo")
        safe_write(self.filename, "foo")

        with open(self.filename) as fp:
            self.assertEqual(fp.read(), "foo")

    def test_simple_callable(self):
        """Test whether the file content is correctly written when using callable."""
        name = self.filename
        safe_write(name, lambda fp: fp.write("foo"))

        with open(name) as fp:
            self.assertEqual(fp.read(), "foo")

    def test_simple_error(self):
        """Test whether the file content is not half written if error happens."""
        name = self.filename
        safe_write(name, "foo")

        def simulate_interrupted(fp):
            fp.write("bar")
            raise KeyboardInterrupt()
            fp.write("foo")

        self.assertRaises(KeyboardInterrupt, safe_write, name, simulate_interrupted)

        with open(name) as fp:
            self.assertEqual(fp.read(), "foo")


class TestUpdatePkgConfig(unittest.TestCase):
    def setUp(self):
        f = tempfile.NamedTemporaryFile(delete=False)
        self.filename = f.name
        f.close()

    def tearDown(self):
        os.remove(self.filename)

    def test_simple(self):
        """Test whether the file content is correctly written when using string."""
        data = """\
prefix=/home/vagrant/pisi/tmp/Qt-4.8.2-2/usr
exec_prefix=${prefix}
libdir=${prefix}/lib
"""

        r_data = """\
prefix=/foo/bar
exec_prefix=${prefix}
libdir=${prefix}/lib
"""
        with tempfile.NamedTemporaryFile(suffix=".pc",
                                         delete=False, mode="wt") as fp:
            pc_file = fp.name
            fp.write(data)
            fp.close()

            update_pkg_config_prefix(pc_file, "/foo/bar")

            with open(pc_file) as r_fp:
                self.assertEqual(r_fp.read(), r_data)

if __name__ == '__main__':
    unittest.main()
