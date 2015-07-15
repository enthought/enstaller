import mock
import sys

from enstaller.errors import InvalidMetadata
from enstaller.pep425 import PythonImplementation

if sys.version_info[0] == 2:
    import unittest2 as unittest
else:
    import unittest


class TestPythonImplementation(unittest.TestCase):
    def test_from_running_python(self):
        # When
        with mock.patch(
            "enstaller.pep425._abbreviated_implementation",
            return_value="cp"
        ):
            with mock.patch("sys.version_info", (2, 7, 9, 'final', 0)):
                py = PythonImplementation.from_running_python()

        # Then
        self.assertEqual(py.pep425_tag, "cp27")

        # When
        with mock.patch("sys.pypy_version_info", "pypy 1.9", create=True):
            with mock.patch("sys.version_info", (2, 7, 9, 'final', 0)):
                py = PythonImplementation.from_running_python()

        # Then
        self.assertEqual(py.pep425_tag, "pp27")

        # When
        with mock.patch("sys.platform", "java 1.7", create=True):
            with mock.patch("sys.version_info", (2, 7, 9, 'final', 0)):
                py = PythonImplementation.from_running_python()

        # Then
        self.assertEqual(py.pep425_tag, "jy27")

        # When
        with mock.patch("sys.platform", "cli", create=True):
            with mock.patch("sys.version_info", (2, 7, 9, 'final', 0)):
                py = PythonImplementation.from_running_python()

        # Then
        self.assertEqual(py.pep425_tag, "ip27")

    def test_errors(self):
        # Given
        s = "cp"

        # When/Then
        with self.assertRaises(InvalidMetadata):
            PythonImplementation.from_string(s)

        # Given
        s = "py2"

        # When/Then
        with self.assertRaises(InvalidMetadata):
            PythonImplementation.from_string(s)

        # Given
        s = "py234"

        # When/Then
        with self.assertRaises(InvalidMetadata):
            PythonImplementation.from_string(s)
