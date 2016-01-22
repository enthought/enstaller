import unittest

from simplesat import Requirement
from enstaller.solver.legacy_requirement import _LegacyRequirement


class TestLegacyRequirement(unittest.TestCase):
    def test_simple(self):
        # Given
        s = "MKL 10.3"
        r_requirement = Requirement.from_legacy_requirement_string(s)

        # When
        requirement = _LegacyRequirement.from_requirement_string(s)

        # Then
        self.assertEqual(requirement._requirement, r_requirement)
        self.assertEqual(requirement.strictness, 2)

        # Given
        s = "MKL 10.3-1"
        r_requirement = Requirement.from_legacy_requirement_string(s)

        # When
        requirement = _LegacyRequirement.from_requirement_string(s)

        # Then
        self.assertEqual(requirement._requirement, r_requirement)
        self.assertEqual(requirement.strictness, 3)

        # Given
        s = "MKL"
        r_requirement = Requirement.from_legacy_requirement_string(s)

        # When
        requirement = _LegacyRequirement.from_requirement_string(s)

        # Then
        self.assertEqual(requirement._requirement, r_requirement)
        self.assertEqual(requirement.strictness, 1)

    def test_invalid(self):
        # Given
        s = "MKL >= 10.3"
        requirement = Requirement._from_string(s)

        # When/Then
        with self.assertRaises(RuntimeError):
            requirement = _LegacyRequirement(requirement)
