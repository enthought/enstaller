from egginst._compat import assertCountEqual
from egginst.vendor.six.moves import unittest

from enstaller import Repository

from enstaller.new_solver import Requirement
from enstaller.package import RepositoryPackageMetadata
from enstaller.repository_info import BroodRepositoryInfo
from enstaller.solver import Request
from enstaller.versions.enpkg import EnpkgVersion

from .._composer_utils import (
    _fix_php_version, _normalize_php_version, _requirement_to_php_string,
    repository_to_composer_json_dict, request_to_php_parts
)


P = RepositoryPackageMetadata._from_pretty_string


class TestVersionConversions(unittest.TestCase):
    def test_fix_php_version(self):
        # Given
        version = EnpkgVersion.from_string("1.0-1")
        r_fixed_version = "1.0-1"

        # When
        fixed = _fix_php_version(version)

        # Then
        self.assertEqual(fixed, r_fixed_version)

    def test_normalize_php_version(self):
        # Given
        version = EnpkgVersion.from_string("10.3-1")
        r_normalized = "10.3.0.0-patch1"

        # When
        normalized = _normalize_php_version(version)

        # Then
        self.assertEqual(normalized, r_normalized)

        # Given
        version = EnpkgVersion.from_string("0.14.1rc1-1")
        r_normalized = "0.14.1.0-patch1"

        # When
        normalized = _normalize_php_version(version)

        # Then
        self.assertEqual(normalized, r_normalized)

        # Given
        version = EnpkgVersion.from_string("2011n-1")
        r_normalized = "2011.14.0.0-patch1"

        # When
        normalized = _normalize_php_version(version)

        # Then
        self.assertEqual(normalized, r_normalized)

    def test_normalize_php_version_constraint(self):
        # Given
        version = EnpkgVersion.from_string("10.3-1")
        r_normalized = "10.3.0.0-patch1"

        # When
        normalized = _normalize_php_version(version)

        # Then
        self.assertEqual(normalized, r_normalized)

        # Given
        version = EnpkgVersion.from_string("10.3")
        r_normalized = "10.3.0.0"


class TestRequirementToPhpString(unittest.TestCase):
    def test_no_constraints(self):
        # Given
        requirement = Requirement._from_string("numpy")
        r_php_string = "*"

        # When
        php_string = _requirement_to_php_string(requirement)

        # Then
        self.assertEqual(php_string, r_php_string)

    def test_single_constraint(self):
        # Given
        requirement = Requirement._from_string("numpy == 1.8.0-1")
        r_php_string = "1.8.0.0-patch1"

        # When
        php_string = _requirement_to_php_string(requirement)

        # Then
        self.assertEqual(php_string, r_php_string)

        # Given
        requirement = Requirement._from_string("numpy ~= 1.8.0")
        r_php_string = "~1.8.0.0"

        # When
        php_string = _requirement_to_php_string(requirement)

        # Then
        self.assertEqual(php_string, r_php_string)


class TestRepositoryToComposerJsonDict(unittest.TestCase):
    def test_simple(self):
        # Given
        repository_info = BroodRepositoryInfo(
            "https://acme.com", "acme/looney")
        repository = Repository([
            P("MKL 10.3-1", repository_info),
        ])

        r_entries = [
            {
                "name": "MKL",
                "require": {},
                "version": "10.3-1",
                "version_normalized": "10.3.0.0-patch1",
            }
        ]

        # When
        entries = list(repository_to_composer_json_dict(repository))

        # Then
        self.assertEqual(entries, r_entries)

    def test_complete(self):
        # Given
        repository_info = BroodRepositoryInfo(
            "https://acme.com", "acme/looney")
        repository = Repository([
            P("MKL 10.3-1", repository_info),
            P("numpy 1.8.1-1; depends (MKL == 10.3-1)", repository_info),
        ])

        r_entries = [
            {
                "name": "MKL",
                "require": {},
                "version": "10.3-1",
                "version_normalized": "10.3.0.0-patch1",
            }, {
                "name": "numpy",
                "require": {
                    "MKL": "10.3.0.0-patch1",
                },
                "version": "1.8.1-1",
                "version_normalized": "1.8.1.0-patch1",
            }
        ]

        # When
        entries = list(repository_to_composer_json_dict(repository))

        # Then
        assertCountEqual(self, entries, r_entries)


class TestRequestToPhpParts(unittest.TestCase):
    def test_no_constraints(self):
        # Given
        request = Request()
        request.install(Requirement._from_string("numpy"))
        r_php_parts = [
            ('install', 'numpy', tuple()),
        ]

        # When
        php_parts = request_to_php_parts(request)

        # Then
        self.assertEqual(php_parts, r_php_parts)

    def test_single_constraint(self):
        # Given
        request = Request()
        request.install(Requirement._from_string("numpy < 1.8"))
        r_php_parts = [
            ('install', 'numpy', ('VersionConstraint("<", "1.8.0.0")',)),
        ]

        # When
        php_parts = request_to_php_parts(request)

        # Then
        self.assertEqual(php_parts, r_php_parts)
