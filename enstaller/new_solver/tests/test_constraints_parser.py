from egginst.vendor.six.moves import unittest

from enstaller.errors import SolverException
from enstaller.versions.enpkg import EnpkgVersion

from ..constraints_parser import _RawConstraintsParser
from ..constraint_types import EnpkgUpstreamMatch, GT, GEQ, LT, LEQ, Not


V = EnpkgVersion.from_string


class Test_RawConstraintsParser(unittest.TestCase):
    def setUp(self):
        self.parser = _RawConstraintsParser()

    def _parse(self, s):
        return self.parser.parse(s, V)

    def test_empty(self):
        # Given
        constraints_string = ""

        # When
        constraints = self._parse(constraints_string)

        # Then
        self.assertEqual(constraints, set())

    def test_simple(self):
        # Given
        constraints_string = "> 1.2.0-1"
        r_constraints = set([GT(V("1.2.0-1"))])

        # When
        constraints = self._parse(constraints_string)

        # Then
        self.assertEqual(constraints, r_constraints)

        # Given
        constraints_string = ">= 1.2.0-1"
        r_constraints = set([GEQ(V("1.2.0-1"))])

        # When
        constraints = self._parse(constraints_string)

        # Then
        self.assertEqual(constraints, r_constraints)

        # Given
        constraints_string = "<= 1.2.0-1"
        r_constraints = set([LEQ(V("1.2.0-1"))])

        # When
        constraints = self._parse(constraints_string)

        # Then
        self.assertEqual(constraints, r_constraints)

        # Given
        constraints_string = "< 1.2.0-1"
        r_constraints = set([LT(V("1.2.0-1"))])

        # When
        constraints = self._parse(constraints_string)

        # Then
        self.assertEqual(constraints, r_constraints)

        # Given
        constraints_string = "~= 1.2.0-1"
        r_constraints = set([EnpkgUpstreamMatch(V("1.2.0-1"))])

        # When
        constraints = self._parse(constraints_string)

        # Then
        self.assertEqual(constraints, r_constraints)

    def test_multiple(self):
        # Given
        constraints_string = ">= 1.2.0-1, < 1.4, != 1.3.8-1"
        r_constraints = set([GEQ(V("1.2.0-1")), LT(V("1.4")),
                             Not(V("1.3.8-1"))])

        # When
        constraints = self._parse(constraints_string)

        # Then
        self.assertEqual(constraints, r_constraints)

    def test_invalid_string(self):
        # Given
        constraints_string = ">= 1.2.0-1 123"

        # When/Then
        with self.assertRaises(SolverException):
            self._parse(constraints_string)
