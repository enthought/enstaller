from egginst.vendor.six.moves import unittest

from enstaller.versions.enpkg import EnpkgVersion

from ..constraint import are_compatible
from ..constraint_types import _VersionConstraint
from ..constraint_types import (Any, EnpkgUpstreamMatch, Equal, GEQ, GT,
                                LEQ, LT, Not)


V = EnpkgVersion.from_string


class TestConstraintMisc(unittest.TestCase):
    def test_repr(self):
        # Given
        constraint = Equal(V("1.2-1"))

        # When/Then
        self.assertTrue(repr(constraint), "Equal('1.2-1')")

    def test_ensure_can_compare(self):
        # Given
        left = Equal(V("1.2-1"))
        class DummyVersion(object):
            pass
        right = Equal(DummyVersion())

        # When/Then
        with self.assertRaises(TypeError):
            self.assertTrue(left.matches(right))

    def test_hashing(self):
        # Given
        v1 = V("1.2.1-1")
        v2 = V("1.2.1-1")

        # When/Then
        self.assertEqual(hash(v1), hash(v2))
        self.assertEqual(hash(GEQ(v1)), hash(GEQ(v2)))


class TestAreCompatible(unittest.TestCase):
    def test_simple_equal(self):
        # Given
        constraint = Equal(V("1.2-1"))
        candidate = V("1.2-1")

        # When/Then
        self.assertTrue(are_compatible(constraint, candidate))

        # Given
        constraint = Equal(V("1.2-1"))
        candidate = V("1.3-1")

        # When/Then
        self.assertFalse(are_compatible(constraint, candidate))

    def test_simple_any(self):
        # Given
        constraint = Any()
        candidate = V("1.2.3-1")

        # When/Then
        self.assertTrue(are_compatible(constraint, candidate))

    def test_simple_leq(self):
        # Given
        constraint = LEQ(V("1.2-2"))
        candidate = V("1.2-1")

        # When/Then
        self.assertTrue(are_compatible(constraint, candidate))

        # Given
        constraint = LEQ(V("1.2-1"))
        candidate = V("1.2-1")

        # When/Then
        self.assertTrue(are_compatible(constraint, candidate))

        # Given
        constraint = LEQ(V("1.1-1"))
        candidate = V("1.2-1")

        # When/Then
        self.assertFalse(are_compatible(constraint, candidate))

    def test_simple_lt(self):
        # Given
        constraint = LT(V("1.2-2"))
        candidate = V("1.2-1")

        # When/Then
        self.assertTrue(are_compatible(constraint, candidate))

        # Given
        constraint = LT(V("1.2-1"))
        candidate = V("1.2-1")

        # When/Then
        self.assertFalse(are_compatible(constraint, candidate))

        # Given
        constraint = LT(V("1.1-1"))
        candidate = V("1.2-1")

        # When/Then
        self.assertFalse(are_compatible(constraint, candidate))

    def test_simple_geq(self):
        # Given
        constraint = GEQ(V("1.2-2"))
        candidate = V("1.2-3")

        # When/Then
        self.assertTrue(are_compatible(constraint, candidate))

        # Given
        constraint = GEQ(V("1.2-1"))
        candidate = V("1.2-1")

        # When/Then
        self.assertTrue(are_compatible(constraint, candidate))

        # Given
        constraint = GEQ(V("1.2-2"))
        candidate = V("1.2-1")

        # When/Then
        self.assertFalse(are_compatible(constraint, candidate))

    def test_simple_gt(self):
        # Given
        constraint = GT(V("1.2-2"))
        candidate = V("1.2-3")

        # When/Then
        self.assertTrue(are_compatible(constraint, candidate))

        # Given
        constraint = GT(V("1.2-1"))
        candidate = V("1.2-1")

        # When/Then
        self.assertFalse(are_compatible(constraint, candidate))

        # Given
        constraint = GT(V("1.2-2"))
        candidate = V("1.2-1")

        # When/Then
        self.assertFalse(are_compatible(constraint, candidate))

    def test_simple_not(self):
        # Given
        constraint = Not(V("1.2-1"))

        # When/Then
        self.assertTrue(are_compatible(constraint, V("1.2-3")))
        self.assertTrue(are_compatible(constraint, V("1.2-2")))
        self.assertTrue(are_compatible(constraint, V("1.2-6")))
        self.assertFalse(are_compatible(constraint, V("1.2-1")))

    def test_simple_enpkg_upstream_match(self):
        # Given
        constraint = EnpkgUpstreamMatch("1.2")

        # When/Then
        self.assertTrue(are_compatible(constraint, V("1.2-3")))
        self.assertTrue(are_compatible(constraint, V("1.2-1")))
        self.assertTrue(are_compatible(constraint, V("1.2-6")))
        self.assertFalse(are_compatible(constraint, V("1.2.1-1")))
        self.assertFalse(are_compatible(constraint, V("1.3-2")))
        self.assertFalse(are_compatible(constraint, V("2.0-3")))
