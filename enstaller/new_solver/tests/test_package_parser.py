import unittest

from enstaller.errors import SolverException
from enstaller.versions.enpkg import EnpkgVersion

from ..constraint_types import Equal
from ..package_parser import PrettyPackageStringParser


V = EnpkgVersion.from_string


class TestPrettyPackageStringParser(unittest.TestCase):
    def test_invalid_formats(self):
        # Given
        parser = PrettyPackageStringParser(V)
        package_string = ""
        r_message = "Invalid preambule: "

        # When
        with self.assertRaisesRegexp(ValueError, r_message):
            parser.parse(package_string)

        # Given
        package_string = "numpy"
        r_message = "Invalid preambule: 'numpy'"

        # When
        with self.assertRaisesRegexp(ValueError, r_message):
            parser.parse(package_string)

        # Given
        package_string = "numpy 1.8.0-1; depends (nose 1.3.2)"
        r_message = "Invalid requirement block: "

        # When
        with self.assertRaisesRegexp(SolverException, r_message):
            parser.parse(package_string)

        # Given
        package_string = "numpy 1.8.0-1; conflicts (nose 1.3.2)"
        r_message = "Invalid constraint block: 'conflicts \(nose 1.3.2\)'"

        # When
        with self.assertRaisesRegexp(ValueError, r_message):
            parser.parse(package_string)

    def test_simple(self):
        # Given
        parser = PrettyPackageStringParser(V)
        package_string = "numpy 1.8.0-1; depends (nose == 1.3.4-1)"

        # When
        name, version, constraints = parser.parse(package_string)

        # Then
        self.assertEqual(name, "numpy")
        self.assertEqual(version, V("1.8.0-1"))
        self.assertTrue("nose" in constraints)
        self.assertEqual(constraints["nose"], {Equal(V("1.3.4-1"))})

    def test_no_dependencies(self):
        # Given
        parser = PrettyPackageStringParser(V)
        package_string = "numpy 1.8.0-1"

        # When
        name, version, constraints = parser.parse(package_string)

        # Then
        self.assertEqual(name, "numpy")
        self.assertEqual(version, V("1.8.0-1"))
        self.assertItemsEqual(constraints, {})

    def test_to_legacy_constraints(self):
        # Given
        parser = PrettyPackageStringParser(V)
        package_string = "numpy 1.8.0-1; depends (nose == 1.3.4-1)"

        # When
        name, version, constraints = parser.parse_to_legacy_constraints(package_string)

        # Then
        self.assertEqual(name, "numpy")
        self.assertEqual(version, V("1.8.0-1"))
        self.assertEqual(constraints, ["nose 1.3.4-1"])

        # Given
        package_string = "numpy 1.8.0-1; depends (nose ~= 1.3.4)"

        # When
        name, version, constraints = parser.parse_to_legacy_constraints(package_string)

        # Then
        self.assertEqual(name, "numpy")
        self.assertEqual(version, V("1.8.0-1"))
        self.assertEqual(constraints, ["nose 1.3.4"])

        # Given
        package_string = "numpy 1.8.0-1; depends (nose)"

        # When
        name, version, constraints = parser.parse_to_legacy_constraints(package_string)

        # Then
        self.assertEqual(name, "numpy")
        self.assertEqual(version, V("1.8.0-1"))
        self.assertEqual(constraints, ["nose"])
