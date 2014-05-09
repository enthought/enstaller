import os
import sys

from os.path import abspath, dirname, join

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from enstaller.repository import Repository, RepositoryPackageMetadata

from enstaller import resolve
from enstaller.resolve import Resolve, Req
from enstaller.indexed_repo.metadata import parse_depend_index


INDEX_REPO_DIR = abspath(join(dirname(__file__), os.pardir, "indexed_repo", "tests"))


def _old_style_index_to_packages(index_path):
    with open(index_path) as fp:
        index_data = fp.read()

    packages = []
    index = parse_depend_index(index_data)
    for key, spec in index.items():
        spec['name'] = spec['name'].lower()
        spec['type'] = 'egg'
        #spec['repo_dispname'] = self.name
        spec['store_location'] = os.path.dirname(index_path)

        package = RepositoryPackageMetadata.from_json_dict(key, spec)
        packages.append(package)

    return packages

def _old_style_indices_to_repository(indices):
    repository = Repository()
    for index in indices:
        for package in _old_style_index_to_packages(index):
            repository.add_package(package)
    return repository


def eggs_rs(c, req_string):
    return c.install_sequence(Req(req_string))


class TestReq(unittest.TestCase):
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
            r = Req(req_string)
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
            r = Req(req_string)
            self.assertEqual(r.as_dict(), d)

    def test_misc_methods(self):
        for req_string in ['', 'foo', 'bar 1.2', 'baz 2.6.7-5']:
            r = Req(req_string)
            self.assertEqual(str(r), req_string)
            self.assertEqual(r, r)
            self.assertEqual(eval(repr(r)), r)

        self.assertNotEqual(Req('foo'), Req('bar'))
        self.assertNotEqual(Req('foo 1.4'), Req('foo 1.4-5'))

    def test_matches(self):
        spec = dict(name='foo_bar', version='2.4.1', build=3, python=None)
        for req_string, m in [
            ('', True),
            ('foo', False),
            ('Foo_BAR', True),
            ('foo_Bar 2.4.1', True),
            ('FOO_Bar 1.8.7', False),
            ('FOO_BAR 2.4.1-3', True),
            ('FOO_Bar 2.4.1-1', False),
            ]:
            self.assertEqual(Req(req_string).matches(spec), m, req_string)

    def test_matches_py(self):
        spec = dict(name='foo', version='2.4.1', build=3, python=None)
        for py in ['2.4', '2.5', '2.6', '3.1']:
            with mock.patch("enstaller.resolve.PY_VER", py):
                self.assertEqual(Req('foo').matches(spec), True)

        spec25 = dict(spec)
        spec25.update(dict(python='2.5'))

        spec26 = dict(spec)
        spec26.update(dict(python='2.6'))

        with mock.patch("enstaller.resolve.PY_VER", "2.5"):
            self.assertEqual(Req('foo').matches(spec25), True)
            self.assertEqual(Req('foo').matches(spec26), False)

        with mock.patch("enstaller.resolve.PY_VER", "2.6"):
            self.assertEqual(Req('foo').matches(spec25), False)
            self.assertEqual(Req('foo').matches(spec26), True)

    def test_from_anything_name(self):
        # Given
        req_arg = "numpy"

        # When
        req = Req.from_anything(req_arg)

        # Then
        self.assertEqualRequirements(req, Req(req_arg))

    def test_from_anything_name_and_version(self):
        # Given
        req_arg = "numpy 1.8.0"

        # When
        req = Req.from_anything(req_arg)

        # Then
        self.assertEqualRequirements(req, Req(req_arg))

    def test_from_anything_name_and_version_and_build(self):
        # Given
        req_arg = "numpy 1.8.0-1"

        # When
        req = Req.from_anything(req_arg)

        # Then
        self.assertEqualRequirements(req, Req(req_arg))

    def test_from_anything_req(self):
        # Given
        req_arg = Req("numpy 1.8.0-1")

        # When
        req = Req.from_anything(req_arg)

        # Then
        self.assertEqualRequirements(req, req_arg)


class TestChain0(unittest.TestCase):
    def setUp(self):
        indices = [join(INDEX_REPO_DIR, fn) for fn in ['index-add.txt',
                                                       'index-5.1.txt',
                                                       'index-5.0.txt',
                                                       'index-cycle.txt']]
        repo = _old_style_indices_to_repository(indices)
        self.resolve = Resolve(repo)

    @mock.patch("enstaller.resolve.PY_VER", "2.5")
    def test_25(self):
        self.assertEqual(eggs_rs(self.resolve, 'SciPy 0.8.0.dev5698'),
                         ['freetype-2.3.7-1.egg', 'libjpeg-7.0-1.egg',
                          'numpy-1.3.0-1.egg', 'PIL-1.1.6-4.egg',
                          'scipy-0.8.0.dev5698-1.egg'])

        self.assertEqual(eggs_rs(self.resolve, 'SciPy'),
                         ['numpy-1.3.0-1.egg', 'scipy-0.8.0-1.egg'])

        self.assertEqual(eggs_rs(self.resolve, 'epdcore'),
                         ['AppInst-2.0.4-1.egg', 'numpy-1.3.0-1.egg',
                          'scipy-0.8.0-1.egg', 'EPDCore-1.2.5-1.egg'])

    @mock.patch("enstaller.resolve.PY_VER", "2.6")
    def test_26(self):
        self.assertEqual(eggs_rs(self.resolve, 'SciPy'),
                         ['numpy-1.3.0-2.egg', 'scipy-0.8.0-2.egg'])

        self.assertEqual(eggs_rs(self.resolve, 'epdcore'),
                         ['numpy-1.3.0-2.egg', 'scipy-0.8.0-2.egg',
                          'EPDCore-2.0.0-1.egg'])

class TestChain1(unittest.TestCase):
    def setUp(self):
        indices = [join(INDEX_REPO_DIR, name, 'index-7.1.txt') for name
                   in ('epd', 'gpl')]
        repo = _old_style_indices_to_repository(indices)
        self.resolve = Resolve(repo)

    def test_get_repo(self):
        for req_string, repo_name in [
            ('MySQL_python', 'gpl'),
            ('bitarray', 'epd'),
            ('foobar', None),
            ]:
            self.resolve.get_egg(Req(req_string))


    @mock.patch("enstaller.resolve.PY_VER", "2.7")
    def test_get_dist(self):
        for req_string, repo_name, egg in [
            ('MySQL_python',  'gpl', 'MySQL_python-1.2.3-2.egg'),
            ('numpy',         'epd', 'numpy-1.6.0-3.egg'),
            ('swig',          'epd', 'swig-1.3.40-2.egg'),
            ('swig 1.3.36',   'epd', 'swig-1.3.36-3.egg'),
            ('swig 1.3.40-1', 'epd', 'swig-1.3.40-1.egg'),
            ('swig 1.3.40-2', 'epd', 'swig-1.3.40-2.egg'),
            ('foobar', None, None),
            ]:
            self.assertEqual(self.resolve.get_egg(Req(req_string)), egg)

    def test_reqs_dist(self):
        self.assertEqual(self.resolve.reqs_egg('FiPy-2.1-1.egg'),
                         set([Req('distribute'),
                              Req('scipy'),
                              Req('numpy'),
                              Req('pysparse 1.2.dev203')]))

    @mock.patch("enstaller.resolve.PY_VER", "2.7")
    def test_root(self):
        self.assertEqual(self.resolve.install_sequence(Req('numpy 1.5.1'),
                                                       mode='root'),
                         ['numpy-1.5.1-2.egg'])

        self.assertEqual(self.resolve.install_sequence(Req('numpy 1.5.1-1'),
                                                       mode='root'),
                         ['numpy-1.5.1-1.egg'])

    @mock.patch("enstaller.resolve.PY_VER", "2.7")
    def test_order1(self):
        self.assertEqual(self.resolve.install_sequence(Req('numpy')),
                         ['MKL-10.3-1.egg', 'numpy-1.6.0-3.egg'])

    @mock.patch("enstaller.resolve.PY_VER", "2.7")
    def test_order2(self):
        self.assertEqual(self.resolve.install_sequence(Req('scipy')),
                         ['MKL-10.3-1.egg', 'numpy-1.5.1-2.egg',
                          'scipy-0.9.0-1.egg'])


class TestChain2(unittest.TestCase):
    def setUp(self):
        indices = [join(INDEX_REPO_DIR, name, 'index-7.1.txt') for name
                   in ('open', 'runner', 'epd')]
        self.repo = _old_style_indices_to_repository(indices)
        self.resolve = Resolve(self.repo)

    @mock.patch("enstaller.resolve.PY_VER", "2.7")
    def test_flat_recur1(self):
        d1 = self.resolve.install_sequence(Req('openepd'), mode='flat')
        d2 = self.resolve.install_sequence(Req('openepd'), mode='recur')
        self.assertEqual(d1, d2)
        d3 = self.resolve.install_sequence(Req('foo'), mode='recur')
        self.assertEqual(d2[:-1], d3[:-1])

    @mock.patch("enstaller.resolve.PY_VER", "2.7")
    def test_flat_recur2(self):
        for rs in 'epd 7.0', 'epd 7.0-1', 'epd 7.0-2':
            d1 = self.resolve.install_sequence(Req(rs), mode='flat')
            d2 = self.resolve.install_sequence(Req(rs), mode='recur')
            self.assertEqual(d1, d2)

    @mock.patch("enstaller.resolve.PY_VER", "2.7")
    def test_multiple_reqs(self):
        lst = self.resolve.install_sequence(Req('ets'))
        self.assert_('numpy-1.5.1-2.egg' in lst)

class TestCycle(unittest.TestCase):
    """Avoid an infinite recursion when the dependencies contain a cycle."""

    def setUp(self):
        indices = [join(INDEX_REPO_DIR, 'index-cycle.txt')]
        repo = _old_style_indices_to_repository(indices)
        self.resolve = Resolve(repo)

    @mock.patch("enstaller.resolve.PY_VER",  "2.5")
    def test_cycle(self):
        try:
            eg = eggs_rs(self.resolve, 'cycleParent 2.0-5')
        except Exception as e:
            self.assertIn("Loop", e.message, "unexpected exception message "+repr(e.message) )
        else:
            self.assertIsNone(eg, "dependency cycle did not trigger an exception "+repr(eg))
