from egginst.vendor.six.moves import unittest

from enstaller.repository import PackageVersionInfo
from enstaller.versions.enpkg import EnpkgVersion

from ..requirement import Requirement


V = EnpkgVersion.from_string


class TestRequirement(unittest.TestCase):
    def assertEqualRequirements(self, left, right):
        self.assertEqual(left.as_dict(), right.as_dict())

    def test_init(self):
        for req_string, name, version, build, strictness in [
                ('',          None,  None,  None, 0),
                (' \t',       None,  None,  None, 0),
                ('foo',       'foo', None,  None, 1),
                (u'bar 1.9',  'bar', '1.9', None, 2),
                ('BAZ 1.8-2', 'baz', '1.8', 2,    3),
                ('qux 1.3-0', 'qux', '1.3', 0,    3),
        ]:
            r = Requirement(req_string)
            self.assertEqual(r.name, name)
            self.assertEqual(r.version, version)
            self.assertEqual(r.build, build)
            self.assertEqual(r.strictness, strictness)

    def test_as_dict(self):
        for req_string, d in [
            ('',          dict()),
            ('foo',       dict(name='foo')),
            ('bar 1.9',   dict(name='bar', version='1.9')),
            ('BAZ 1.8-2', dict(name='baz', version='1.8', build=2)),
        ]:
            r = Requirement(req_string)
            self.assertEqual(r.as_dict(), d)

    def test_misc_methods(self):
        for req_string in ['', 'foo', 'bar 1.2', 'baz 2.6.7-5']:
            r = Requirement(req_string)
            self.assertEqual(str(r), req_string)
            self.assertEqual(r, r)
            self.assertEqual(eval(repr(r)), r)

        self.assertNotEqual(Requirement('foo'), Requirement('bar'))
        self.assertNotEqual(Requirement('foo 1.4'), Requirement('foo 1.4-5'))

    def test_matches(self):
        spec = PackageVersionInfo('foo_bar', V('2.4.1-3'))
        for req_string, m in [
            ('', True),
            ('foo', False),
            ('Foo_BAR', True),
            ('foo_Bar 2.4.1', True),
            ('FOO_Bar 1.8.7', False),
            ('FOO_BAR 2.4.1-3', True),
            ('FOO_Bar 2.4.1-1', False),
        ]:
            self.assertEqual(Requirement(req_string).matches(spec), m, req_string)

    def test_from_anything_name(self):
        # Given
        req_arg = "numpy"

        # When
        req = Requirement.from_anything(req_arg)

        # Then
        self.assertEqualRequirements(req, Requirement(req_arg))

    def test_from_anything_name_and_version(self):
        # Given
        req_arg = "numpy 1.8.0"

        # When
        req = Requirement.from_anything(req_arg)

        # Then
        self.assertEqualRequirements(req, Requirement(req_arg))

    def test_from_anything_name_and_version_and_build(self):
        # Given
        req_arg = "numpy 1.8.0-1"

        # When
        req = Requirement.from_anything(req_arg)

        # Then
        self.assertEqualRequirements(req, Requirement(req_arg))

    def test_from_anything_req(self):
        # Given
        req_arg = Requirement("numpy 1.8.0-1")

        # When
        req = Requirement.from_anything(req_arg)

        # Then
        self.assertEqualRequirements(req, req_arg)
