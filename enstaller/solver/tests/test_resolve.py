import mock

from egginst._compat import TestCase
from enstaller.repository import Repository
from enstaller.tests.common import (create_repositories,
                                    dummy_repository_package_factory)

from ..requirement import Requirement
from ..resolve import Resolve


class TestResolve(TestCase):
    def _repository_factory(self, packages):
        repository = Repository()
        for p in packages:
            repository.add_package(p)
        return repository

    def test__latest_egg_simple(self):
        # Given
        packages = [
                dummy_repository_package_factory("swig", "1.3.40", 1),
                dummy_repository_package_factory("swig", "1.3.40", 2),
                dummy_repository_package_factory("swig", "2.0.1", 1),
        ]
        repository = self._repository_factory(packages)

        # When
        resolver = Resolve(repository)
        latest = resolver._latest_egg(Requirement("swig"))

        # Then
        self.assertEqual(latest, "swig-2.0.1-1.egg")

        # When
        resolver = Resolve(repository)
        latest = resolver._latest_egg(Requirement("swigg"))

        # Then
        self.assertIsNone(latest)


    def test__latest_egg_multiple_python_versions(self):
        # Given
        packages = [
                dummy_repository_package_factory("swig", "1.3.40", 1),
                dummy_repository_package_factory("swig", "1.3.40", 2),
                dummy_repository_package_factory("swig", "2.0.1", 1,
                                                 py_ver="2.4"),
        ]
        repository = self._repository_factory(packages)

        # When
        resolver = Resolve(repository)
        latest = resolver._latest_egg(Requirement("swig"))

        # Then
        self.assertEqual(latest, "swig-1.3.40-2.egg")
