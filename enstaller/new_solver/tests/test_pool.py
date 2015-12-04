import sys

import os.path

from egginst._compat import assertCountEqual

from enstaller.versions import EnpkgVersion

from ..pool import Pool
from ..requirement import Requirement

from .common import DATA_DIR, repository_from_index

if sys.version_info[0] == 2:
    import unittest2 as unittest
else:
    import unittest


V = EnpkgVersion.from_string


class TestPool(unittest.TestCase):
    def test_what_provides_tilde(self):
        # Given
        index_path = os.path.join(DATA_DIR, "numpy_index.json")
        repository = repository_from_index(index_path)
        requirement = Requirement._from_string("numpy ~= 1.8.1")

        # When
        pool = Pool([repository])
        candidates = pool.what_provides(requirement)

        # Then
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].full_version, "1.8.1-1")

    def test_what_provides_casing(self):
        # Given
        index_path = os.path.join(DATA_DIR, "numpy_index.json")
        repository = repository_from_index(index_path)
        requirement = Requirement._from_string("mkl ~= 10.2")

        # When
        pool = Pool([repository])
        candidates = pool.what_provides(requirement)
        versions = [candidate.full_version for candidate in candidates]

        # Then
        assertCountEqual(self, versions, ["10.2-1", "10.2-2"])

    def test_what_provides_simple(self):
        # Given
        index_path = os.path.join(DATA_DIR, "numpy_index.json")
        repository = repository_from_index(index_path)
        requirement = Requirement._from_string("numpy >= 1.8.0")

        # When
        pool = Pool([repository])
        candidates = pool.what_provides(requirement)
        versions = [candidate.full_version for candidate in candidates]

        # Then
        assertCountEqual(self, versions,
                         ["1.8.0-1", "1.8.0-2", "1.8.0-3", "1.8.1-1"])

    def test_id_to_string(self):
        # Given
        index_path = os.path.join(DATA_DIR, "numpy_index.json")
        repository = repository_from_index(index_path)
        requirement = Requirement._from_string("numpy >= 1.8.1")

        # When
        pool = Pool([repository])
        candidate = pool.what_provides(requirement)[0]
        package_id = pool.package_id(candidate)

        # Then
        self.assertEqual(pool.id_to_string(package_id), "+numpy-1.8.1-1")
        self.assertEqual(pool.id_to_string(-package_id), "-numpy-1.8.1-1")
