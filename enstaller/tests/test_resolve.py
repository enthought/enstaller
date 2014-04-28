import os
import sys

from collections import defaultdict
from os.path import abspath, dirname, join

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from enstaller.repository import Repository
from enstaller.store.indexed import IndexedStore
from enstaller.store.joined import JoinedStore

from enstaller import resolve
from enstaller.resolve import Resolve, Req
from enstaller.indexed_repo.metadata import parse_depend_index


INDEX_REPO_DIR = abspath(join(dirname(__file__), os.pardir, "indexed_repo", "tests"))


class DummyStore(IndexedStore):

    def __init__(self, index_path, name=None):
        self.index_path = index_path
        self.name = name
        super(DummyStore, self).__init__()

    def connect(self, auth=None):
        index_data = open(self.index_path).read()
        self._connected = True
        self._index = parse_depend_index(index_data)
        for spec in self._index.itervalues():
            spec['name'] = spec['name'].lower()
            spec['type'] = 'egg'
            spec['repo_dispname'] = self.name
        self._groups = defaultdict(list)
        for key, info in self._index.iteritems():
            self._groups[info['name']].append(key)

    def get_data(self, key):
        pass

    def info(self):
        pass

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
            resolve.PY_VER = py
            self.assertEqual(Req('foo').matches(spec), True)

        spec25 = dict(spec)
        spec25.update(dict(python='2.5'))

        spec26 = dict(spec)
        spec26.update(dict(python='2.6'))

        resolve.PY_VER = '2.5'
        self.assertEqual(Req('foo').matches(spec25), True)
        self.assertEqual(Req('foo').matches(spec26), False)

        resolve.PY_VER = '2.6'
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
        store = JoinedStore([ DummyStore(join(INDEX_REPO_DIR, fn)) for fn in
                             ['index-add.txt', 'index-5.1.txt',
                              'index-5.0.txt', 'index-cycle.txt']])
        repo = Repository(store)
        repo.connect((None, None))
        self.resolve = Resolve(repo)

    def test_25(self):
        resolve.PY_VER = '2.5'
        self.assertEqual(eggs_rs(self.resolve, 'SciPy 0.8.0.dev5698'),
                         ['freetype-2.3.7-1.egg', 'libjpeg-7.0-1.egg',
                          'numpy-1.3.0-1.egg', 'PIL-1.1.6-4.egg',
                          'scipy-0.8.0.dev5698-1.egg'])

        self.assertEqual(eggs_rs(self.resolve, 'SciPy'),
                         ['numpy-1.3.0-1.egg', 'scipy-0.8.0-1.egg'])

        self.assertEqual(eggs_rs(self.resolve, 'epdcore'),
                         ['AppInst-2.0.4-1.egg', 'numpy-1.3.0-1.egg',
                          'scipy-0.8.0-1.egg', 'EPDCore-1.2.5-1.egg'])

    def test_26(self):
        resolve.PY_VER = '2.6'

        self.assertEqual(eggs_rs(self.resolve, 'SciPy'),
                         ['numpy-1.3.0-2.egg', 'scipy-0.8.0-2.egg'])

        self.assertEqual(eggs_rs(self.resolve, 'epdcore'),
                         ['numpy-1.3.0-2.egg', 'scipy-0.8.0-2.egg',
                          'EPDCore-2.0.0-1.egg'])

class TestChain1(unittest.TestCase):
    def setUp(self):
        store = JoinedStore([
                DummyStore(join(INDEX_REPO_DIR, name, 'index-7.1.txt'), name)
                for name in ('epd', 'gpl')])
        repo = Repository(store)
        repo.connect((None, None))
        self.resolve = Resolve(repo)

        self.store = store

        resolve.PY_VER = '2.7'

    def test_get_repo(self):
        for req_string, repo_name in [
            ('MySQL_python', 'gpl'),
            ('bitarray', 'epd'),
            ('foobar', None),
            ]:
            egg = self.resolve.get_egg(Req(req_string))
            if egg is not None:
                self.assertEqual(
                    self.store.get_metadata(egg).get('repo_dispname'),
                    repo_name)

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
            if egg is not None:
                self.assertEqual(
                    self.store.get_metadata(egg).get('repo_dispname'),
                    repo_name)

    def test_reqs_dist(self):
        self.assertEqual(self.resolve.reqs_egg('FiPy-2.1-1.egg'),
                         set([Req('distribute'),
                              Req('scipy'),
                              Req('numpy'),
                              Req('pysparse 1.2.dev203')]))

    def test_root(self):
        self.assertEqual(self.resolve.install_sequence(Req('numpy 1.5.1'),
                                                       mode='root'),
                         ['numpy-1.5.1-2.egg'])

        self.assertEqual(self.resolve.install_sequence(Req('numpy 1.5.1-1'),
                                                       mode='root'),
                         ['numpy-1.5.1-1.egg'])

    def test_order1(self):
        self.assertEqual(self.resolve.install_sequence(Req('numpy')),
                         ['MKL-10.3-1.egg', 'numpy-1.6.0-3.egg'])

    def test_order2(self):
        self.assertEqual(self.resolve.install_sequence(Req('scipy')),
                         ['MKL-10.3-1.egg', 'numpy-1.5.1-2.egg',
                          'scipy-0.9.0-1.egg'])


class TestChain2(unittest.TestCase):
    def setUp(self):
        self.store = JoinedStore([ DummyStore(join(INDEX_REPO_DIR, name,
                                                   'index-7.1.txt'), name) for
                                  name in ('open', 'runner', 'epd')])
        self.repo = Repository(self.store)
        self.repo.connect((None, None))
        self.resolve = Resolve(self.repo)

    def test_flat_recur1(self):
        d1 = self.resolve.install_sequence(Req('openepd'), mode='flat')
        d2 = self.resolve.install_sequence(Req('openepd'), mode='recur')
        self.assertEqual(d1, d2)
        d3 = self.resolve.install_sequence(Req('foo'), mode='recur')
        self.assertEqual(d2[:-1], d3[:-1])

    def test_flat_recur2(self):
        for rs in 'epd 7.0', 'epd 7.0-1', 'epd 7.0-2':
            d1 = self.resolve.install_sequence(Req(rs), mode='flat')
            d2 = self.resolve.install_sequence(Req(rs), mode='recur')
            self.assertEqual(d1, d2)

    def test_multiple_reqs(self):
        lst = self.resolve.install_sequence(Req('ets'))
        self.assert_('numpy-1.5.1-2.egg' in lst)
        self.assertEqual(
            self.store.get_metadata('numpy-1.5.1-2.egg').get('repo_dispname'),
            'epd')

class TestCycle(unittest.TestCase):
    """Avoid an infinite recursion when the dependencies contain a cycle."""

    def setUp(self):
        store = JoinedStore([ DummyStore(join(INDEX_REPO_DIR,
                                              'index-cycle.txt'))])
        repo = Repository(store)
        repo.connect((None, None))
        self.resolve = Resolve(repo)

    def test_cycle(self):
        resolve.PY_VER = '2.5'
        try:
            eg = eggs_rs(self.resolve, 'cycleParent 2.0-5')
        except Exception as e:
            self.assertIn("Loop", e.message, "unexpected exception message "+repr(e.message) )
        else:
            self.assertIsNone(eg, "dependency cycle did not trigger an exception "+repr(eg))
