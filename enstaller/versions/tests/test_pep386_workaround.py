from egginst._compat import TestCase

from ..pep386_workaround import PEP386WorkaroundVersion


class TestPEP386Workaround(TestCase):
    def test_correct_equal(self):
        # Given
        left = PEP386WorkaroundVersion.from_string("1.3.0")
        right = PEP386WorkaroundVersion.from_string("1.3.0")

        # When/Then
        self.assertEqual(left, right)
        self.assertTrue(left == right)
        self.assertFalse(left != right)
        self.assertTrue(left <= right)
        self.assertTrue(left >= right)
        self.assertFalse(left < right)
        self.assertFalse(left > right)

    def test_correct_greater(self):
        # Given
        left = PEP386WorkaroundVersion.from_string("1.2.0")
        right = PEP386WorkaroundVersion.from_string("1.3.0")

        # When/Then
        self.assertFalse(left == right)
        self.assertTrue(left != right)
        self.assertTrue(left <= right)
        self.assertFalse(left >= right)
        self.assertTrue(left < right)
        self.assertFalse(left > right)

    def test_correct_lesser(self):
        # Given
        left = PEP386WorkaroundVersion.from_string("1.3.0")
        right = PEP386WorkaroundVersion.from_string("1.2.0")

        # When/Then
        self.assertFalse(left == right)
        self.assertTrue(left != right)
        self.assertFalse(left <= right)
        self.assertTrue(left >= right)
        self.assertFalse(left < right)
        self.assertTrue(left > right)

    def test_incorrect_equal(self):
        # Given
        left = PEP386WorkaroundVersion.from_string("2010k")
        right = PEP386WorkaroundVersion.from_string("2010k")

        # When/Then
        self.assertEqual(left, right)
        self.assertTrue(left == right)
        self.assertFalse(left != right)
        self.assertTrue(left <= right)
        self.assertTrue(left >= right)
        self.assertFalse(left < right)
        self.assertFalse(left > right)

    def test_incorrect_greater(self):
        # Given
        left = PEP386WorkaroundVersion.from_string("2010i")
        right = PEP386WorkaroundVersion.from_string("2010k")

        # When/Then
        self.assertFalse(left == right)
        self.assertTrue(left != right)
        self.assertTrue(left <= right)
        self.assertFalse(left >= right)
        self.assertTrue(left < right)
        self.assertFalse(left > right)

    def test_incorrect_lesser(self):
        # Given
        left = PEP386WorkaroundVersion.from_string("2010k")
        right = PEP386WorkaroundVersion.from_string("2010i")

        # When/Then
        self.assertFalse(left == right)
        self.assertTrue(left != right)
        self.assertFalse(left <= right)
        self.assertTrue(left >= right)
        self.assertFalse(left < right)
        self.assertTrue(left > right)

    def test_correct_incorrect(self):
        # Given
        left = PEP386WorkaroundVersion.from_string("1.3.0")
        right = PEP386WorkaroundVersion.from_string("1.4.0k")

        # When/Then
        self.assertNotEqual(left, right)
        self.assertFalse(left == right)
        self.assertTrue(left != right)
        self.assertFalse(left <= right)
        self.assertTrue(left >= right)
        self.assertFalse(left < right)
        self.assertTrue(left > right)

        # Given
        left = PEP386WorkaroundVersion.from_string("1.4.0k")
        right = PEP386WorkaroundVersion.from_string("1.3.0")

        # When/Then
        self.assertNotEqual(left, right)
        self.assertFalse(left == right)
        self.assertTrue(left != right)
        self.assertTrue(left <= right)
        self.assertFalse(left >= right)
        self.assertTrue(left < right)
        self.assertFalse(left > right)


    def test_roundtrip_workedaround(self):
        # Given
        version_string = "2011g"

        # When
        version = PEP386WorkaroundVersion.from_string(version_string)

        # Then
        self.assertTrue(version._is_worked_around)
        self.assertEqual(str(version), version_string)


class TestTrailingZeros(TestCase):
    def test_leading_zeros(self):
        # Given
        left = PEP386WorkaroundVersion.from_string("0.9.8")
        right = PEP386WorkaroundVersion.from_string("1.0.1")

        # When/Then
        self.assertTrue(left < right)
        self.assertTrue(left <= right)
        self.assertFalse(left > right)
        self.assertFalse(left >= right)

    def test_round_trip(self):
        # Given
        version_string = "1.3.0"

        # When
        version = PEP386WorkaroundVersion.from_string(version_string)

        # Then
        self.assertEqual(str(version), version_string)

    def test_simple(self):
        # Given
        left = PEP386WorkaroundVersion.from_string("1.3.0")
        right = PEP386WorkaroundVersion.from_string("1.3")

        # When/Then
        self.assertEqual(left, right)
        self.assertTrue(left == right)
        self.assertFalse(left < right)
        self.assertTrue(left <= right)
        self.assertFalse(left > right)
        self.assertTrue(left >= right)

        # Given
        left = PEP386WorkaroundVersion.from_string("1.0.0")
        right = PEP386WorkaroundVersion.from_string("1")

        # When/Then
        self.assertEqual(left, right)
        self.assertTrue(left == right)
        self.assertFalse(left < right)
        self.assertTrue(left <= right)
        self.assertFalse(left > right)
        self.assertTrue(left >= right)

    def test_all_zeros(self):
        # Given
        version_string = "0.0.0"

        # When
        v = PEP386WorkaroundVersion.from_string(version_string)

        # Then
        self.assertEqual(str(v), version_string)


class TestOldCases(TestCase):
    def test_single_number(self):
        # Given
        version_string = "214"
        r_version = PEP386WorkaroundVersion.from_string("214.0.0")

        # When
        version = PEP386WorkaroundVersion.from_string(version_string)

        # Then
        self.assertEqual(version, r_version)
        self.assertEqual(str(version), version_string)

    def test_dev_tag_without_number(self):
        # Given
        r_version = PEP386WorkaroundVersion.from_string("1.0.0.dev1")
        version_string = "1.0.0.dev"

        # When
        version = PEP386WorkaroundVersion.from_string(version_string)

        # Then
        self.assertEqual(version, r_version)
