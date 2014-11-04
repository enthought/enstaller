from __future__ import absolute_import

import os

from os.path import abspath, dirname, join

from enstaller.repository import Repository, RepositoryPackageMetadata
from enstaller.utils import PY_VER
from egginst.vendor.six.moves import unittest

from enstaller.indexed_repo.metadata import parse_depend_index

from ..resolve import Resolve
from ..requirement import Requirement


INDEX_REPO_DIR = abspath(join(dirname(__file__), os.pardir, os.pardir,
                              "indexed_repo", "tests"))


def _old_style_index_to_packages(index_path, python_version):
    with open(index_path) as fp:
        index_data = fp.read()

    packages = []
    index = parse_depend_index(index_data)
    for key, spec in index.items():
        spec['name'] = spec['name'].lower()
        spec['type'] = 'egg'
        spec['store_location'] = os.path.dirname(index_path)

        if python_version == "*":
            package = RepositoryPackageMetadata.from_json_dict(key, spec)
            packages.append(package)
        elif spec["python"] in (None, python_version):
            package = RepositoryPackageMetadata.from_json_dict(key, spec)
            packages.append(package)

    return packages


def _old_style_indices_to_repository(indices, python_version=PY_VER):
    repository = Repository()
    for index in indices:
        for package in _old_style_index_to_packages(index, python_version):
            repository.add_package(package)
    return repository


def eggs_rs(c, req_string):
    return c.install_sequence(Requirement(req_string))


class TestChain0(unittest.TestCase):
    def _resolve_factory(self, python_version):
        indices = [join(INDEX_REPO_DIR, fn) for fn in ['index-add.txt',
                                                       'index-5.1.txt',
                                                       'index-5.0.txt',
                                                       'index-cycle.txt']]
        repo = _old_style_indices_to_repository(indices, python_version)
        return Resolve(repo)

    def test_25(self):
        resolve = self._resolve_factory("2.5")
        self.assertEqual(eggs_rs(resolve, 'SciPy 0.8.0.dev5698'),
                         ['freetype-2.3.7-1.egg', 'libjpeg-7.0-1.egg',
                          'numpy-1.3.0-1.egg', 'PIL-1.1.6-4.egg',
                          'scipy-0.8.0.dev5698-1.egg'])

        self.assertEqual(eggs_rs(resolve, 'SciPy'),
                         ['numpy-1.3.0-1.egg', 'scipy-0.8.0-1.egg'])

        self.assertEqual(eggs_rs(resolve, 'epdcore'),
                         ['AppInst-2.0.4-1.egg', 'numpy-1.3.0-1.egg',
                          'scipy-0.8.0-1.egg', 'EPDCore-1.2.5-1.egg'])

    def test_26(self):
        resolve = self._resolve_factory("2.6")
        self.assertEqual(eggs_rs(resolve, 'SciPy'),
                         ['numpy-1.3.0-2.egg', 'scipy-0.8.0-2.egg'])

        self.assertEqual(eggs_rs(resolve, 'epdcore'),
                         ['numpy-1.3.0-2.egg', 'scipy-0.8.0-2.egg',
                          'EPDCore-2.0.0-1.egg'])


class TestChain1(unittest.TestCase):
    def _resolve_factory(self, python_version=PY_VER):
        indices = [join(INDEX_REPO_DIR, name, 'index-7.1.txt') for name
                   in ('epd', 'gpl')]
        repo = _old_style_indices_to_repository(indices, python_version)
        return Resolve(repo)

    def test_get_repo(self):
        resolve = self._resolve_factory()
        for req_string, repo_name in [
            ('MySQL_python', 'gpl'),
            ('bitarray', 'epd'),
            ('foobar', None),
        ]:
            resolve._latest_egg(Requirement(req_string))

    def test_get_dist(self):
        resolve = self._resolve_factory("2.7")
        for req_string, repo_name, egg in [
            ('MySQL_python',  'gpl', 'MySQL_python-1.2.3-2.egg'),
            ('numpy',         'epd', 'numpy-1.6.0-3.egg'),
            ('swig',          'epd', 'swig-1.3.40-2.egg'),
            ('swig 1.3.36',   'epd', 'swig-1.3.36-3.egg'),
            ('swig 1.3.40-1', 'epd', 'swig-1.3.40-1.egg'),
            ('swig 1.3.40-2', 'epd', 'swig-1.3.40-2.egg'),
            ('foobar', None, None),
        ]:
            self.assertEqual(resolve._latest_egg(Requirement(req_string)), egg)

    def test_reqs_dist(self):
        resolve = self._resolve_factory("*")
        self.assertEqual(resolve._dependencies_from_egg('FiPy-2.1-1.egg'),
                         set([Requirement('distribute'),
                              Requirement('scipy'),
                              Requirement('numpy'),
                              Requirement('pysparse 1.2.dev203')]))

    def test_root(self):
        resolve = self._resolve_factory("2.7")
        self.assertEqual(resolve.install_sequence(Requirement('numpy 1.5.1'),
                                                  mode='root'),
                         ['numpy-1.5.1-2.egg'])

        self.assertEqual(resolve.install_sequence(Requirement('numpy 1.5.1-1'),
                                                  mode='root'),
                         ['numpy-1.5.1-1.egg'])

    def test_order1(self):
        resolve = self._resolve_factory("2.7")
        self.assertEqual(resolve.install_sequence(Requirement('numpy')),
                         ['MKL-10.3-1.egg', 'numpy-1.6.0-3.egg'])

    def test_order2(self):
        resolve = self._resolve_factory("2.7")
        self.assertEqual(resolve.install_sequence(Requirement('scipy')),
                         ['MKL-10.3-1.egg', 'numpy-1.5.1-2.egg',
                          'scipy-0.9.0-1.egg'])


class TestChain2(unittest.TestCase):
    def _resolve_factory(self, python_version=PY_VER):
        indices = [join(INDEX_REPO_DIR, name, 'index-7.1.txt') for name
                   in ('open', 'runner', 'epd')]
        self.repo = _old_style_indices_to_repository(indices, python_version)

        return Resolve(self.repo)

    def test_flat_recur1(self):
        resolve = self._resolve_factory("2.7")
        d1 = resolve.install_sequence(Requirement('openepd'), mode='flat')
        d2 = resolve.install_sequence(Requirement('openepd'), mode='recur')
        self.assertEqual(d1, d2)
        d3 = resolve.install_sequence(Requirement('foo'), mode='recur')
        self.assertEqual(d2[:-1], d3[:-1])

    def test_flat_recur2(self):
        resolve = self._resolve_factory("2.7")
        for rs in 'epd 7.0', 'epd 7.0-1', 'epd 7.0-2':
            d1 = resolve.install_sequence(Requirement(rs), mode='flat')
            d2 = resolve.install_sequence(Requirement(rs), mode='recur')
            self.assertEqual(d1, d2)

    def test_multiple_reqs(self):
        resolve = self._resolve_factory("2.7")
        lst = resolve.install_sequence(Requirement('ets'))
        self.assert_('numpy-1.5.1-2.egg' in lst)


class TestCycle(unittest.TestCase):
    """Avoid an infinite recursion when the dependencies contain a cycle."""

    def _resolve_factory(self, python_version):
        indices = [join(INDEX_REPO_DIR, 'index-cycle.txt')]
        repo = _old_style_indices_to_repository(indices, python_version)
        return Resolve(repo)

    def test_cycle(self):
        resolve = self._resolve_factory("2.5")
        try:
            eg = eggs_rs(resolve, 'cycleParent 2.0-5')
        except Exception as e:
            self.assertIn("Loop", str(e),
                          "unexpected exception message " + repr(e))
        else:
            self.assertIsNone(eg,
                              "dependency cycle did not trigger an exception "
                              + repr(eg))
