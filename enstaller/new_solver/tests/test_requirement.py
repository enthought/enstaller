from egginst.vendor.six.moves import unittest

from enstaller.errors import SolverException
from enstaller.versions.enpkg import EnpkgVersion
from ..requirement import Requirement


V = EnpkgVersion.from_string


class TestRequirement(unittest.TestCase):
    def test_hashing(self):
        # Given
        requirement_string = "numpy >= 1.8.1-3, numpy < 1.9.0"

        # When
        requirement1 = Requirement._from_string(requirement_string)
        requirement2 = Requirement._from_string(requirement_string)

        # Then
        self.assertEqual(requirement1, requirement2)
        self.assertEqual(hash(requirement1), hash(requirement2))

    def test_simple(self):
        # Given
        requirement_string = "numpy >= 1.8.1-3, numpy < 1.9.0"

        # When
        requirement = Requirement._from_string(requirement_string)

        # Then
        self.assertFalse(requirement.matches(V("1.8.1-2")))
        self.assertTrue(requirement.matches(V("1.8.1-3")))
        self.assertTrue(requirement.matches(V("1.8.2-1")))
        self.assertFalse(requirement.matches(V("1.9.0-1")))

    def test_multiple_fails(self):
        # Given
        requirement_string = "numpy >= 1.8.1-3, scipy < 1.9.0"

        # When
        with self.assertRaises(SolverException):
            Requirement._from_string(requirement_string)
