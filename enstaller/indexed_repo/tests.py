import random
import unittest

from utils import (_split_old_version, _split_old_eggname,
                   comparable_version, comparable_spec, split_dist)
from requirement import Req


class TestUtils(unittest.TestCase):

    def test_split_dist(self):
        for repo, fn in [
            ('local:', 'foo.egg'),
            ('http://www.example.com/repo/', 'foo.egg'),
            ('file:///home/repo/', 'numpy-1.1.1-5.egg'),
            ('file://E:\\eggs\\', 'numpy-1.1.1-5.egg'),
            ('file://C:\\Desk and Top\\', 'with space.egg'),
            ]:
            dist = repo + fn
            self.assertEqual(split_dist(dist), (repo, fn))

        for dist in ['local:/foo.egg', '', 'foo.egg', 'file:///usr/']:
            self.assertRaises(AssertionError, split_dist, dist)

    def test_split_old_version(self):
        self.assertEqual(_split_old_version('1.1.0n3'), ('1.1.0', 3))
        self.assertEqual(_split_old_version('2008cn1'), ('2008c', 1))
        self.assertEqual(_split_old_version('2nn2'), ('2n', 2))
        self.assertEqual(_split_old_version('1.1n'), ('1.1n', None))

    def test_split_old_eggname(self):
        fn = 'grin-1.1.1n2-py2.5.egg'
        self.assertEqual(_split_old_eggname(fn), ('grin', '1.1.1', 2))
        fn = 'grin-1.1.1-py2.5.egg'
        self.assertRaises(AssertionError, _split_old_eggname, fn)

    def test_comparable_version(self):
        versions = ['1.0.4', '1.2.1', '1.3.0b1', '1.3.0', '1.3.10']
        org = list(versions)
        random.shuffle(versions)
        versions.sort(key=comparable_version)
        self.assertEqual(versions, org)

        versions = ['2008j', '2008k', '2009b', '2009h']
        org = list(versions)
        random.shuffle(versions)
        versions.sort(key=comparable_version)
        self.assertEqual(versions, org)

    def test_comparable_spec(self):
        s1 = comparable_spec(dict(version='2008j', build=1))
        s2 = comparable_spec(dict(version='2008j', build=2))
        s3 = comparable_spec(dict(version='2009c', build=1))
        self.assert_(s1 < s2 < s3)

        s1 = comparable_spec(dict(version='0.7.0', build=1))
        s2 = comparable_spec(dict(version='0.8.0.dev5876', build=2))
        s3 = comparable_spec(dict(version='0.8.0', build=1))
        self.assert_(s1 < s2 < s3)


class TestReq(unittest.TestCase):

    def test_misc_methods(self):
        for req_string, n in [
            ('', 0),
            ('foo', 1),
            ('foo 1.8', 2),
            ('foo 1.8, 1.9', 2),
            ('foo 1.8-7', 3)
            ]:
            r = Req(req_string)
            if r.strictness >= 1:
                self.assertEqual(r.name, 'foo')
            self.assertEqual(r.strictness, n)
            self.assertEqual(str(r), req_string)
            self.assertEqual(r, r)
            self.assertEqual(eval(repr(r)), r)

    def test_versions(self):
        for req_string, versions in [
            ('foo 1.8', ['1.8']),
            ('foo 2.3 1.8', ['1.8', '2.3']),
            ('foo 4.0.1, 2.3, 1.8', ['1.8', '2.3', '4.0.1']),
            ('foo 1.8-7', ['1.8-7'])
            ]:
            r = Req(req_string)
            self.assertEqual(r.versions, versions)

    def test_matches(self):
        spec = dict(
            metadata_version = '1.1',
            name = 'foo-bar',
            version = '2.4.1',
            build = 3,
        )
        for req_string, m in [
            ('', True),
            ('foo', False),
            ('Foo-BAR', True),
            ('foo-Bar 2.4.1', True),
            ('foo-Bar 2.4.0 2.4.1', True),
            ('foo-Bar 2.4.0 2.4.3', False),
            ('FOO-Bar 1.8.7', False),
            ('FOO-BAR 2.4.1-3', True),
            ('FOO-Bar 2.4.1-1', False),
            ]:
            r = Req(req_string)
            self.assertEqual(r.matches(spec), m)

    def test_as_setuptools(self):
        for s1, s2 in [
            ('foo', 'foo'),
            ('bar 1.8', 'bar >=1.8'),
            ('bar 1.8 2.0', 'bar >=1.8'),
            ('baz 1.3.1-7', 'baz ==1.3.1n7')
            ]:
            r = Req(s1)
            self.assertEqual(r.as_setuptools(), s2)


if __name__ == '__main__':
    unittest.main()
