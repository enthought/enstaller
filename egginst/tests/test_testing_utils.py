import os
import shutil
import tempfile

from egginst._compat import assertCountEqual
from egginst.testing_utils import ControlledEnv, assert_same_fs
from egginst.vendor.six.moves import unittest


class TestControlledEnv(unittest.TestCase):
    def test_simple(self):
        # Given
        env = ControlledEnv()

        # When
        env["key"] = "value"

        # Then
        self.assertEqual(env["key"], "value")

    def test_keys(self):
        # Given
        env = ControlledEnv()

        # When
        env["key1"] = "value1"
        env["key2"] = "value2"

        # Then
        assertCountEqual(self, env.keys(), list(os.environ.keys()) + ["key1", "key2"])

    def test_get_item(self):
        # Given
        env = ControlledEnv(["ignored_key"])

        # When/Then
        with self.assertRaises(KeyError):
            env["ignored_key"]

    def test_custom_env(self):
        # Given
        env = ControlledEnv(environ={"key1": "value1"})

        # When/Then
        self.assertFalse(list(os.environ.keys())[0] in env)


class TestAssertSameFs(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.scratch)

    def test_empty(self):
        # When/Then
        with assert_same_fs(self, self.scratch):
            pass

    def test_simple(self):
        # When/Then
        with assert_same_fs(self, self.scratch):
            path = os.path.join(self.scratch, "yo")
            with open(path, "w") as fp:
                fp.write("")
            os.unlink(path)

        # When/Then
        with self.assertRaises(AssertionError):
            with assert_same_fs(self, self.scratch):
                path = os.path.join(self.scratch, "yo")
                with open(path, "w") as fp:
                    fp.write("")

    def test_remove_file(self):
        # Given
        path = os.path.join(self.scratch, "yo")
        with open(path, "w") as fp:
            fp.write("")

        # When/Then
        with assert_same_fs(self, self.scratch):
            self.assertTrue(os.path.exists(path))
