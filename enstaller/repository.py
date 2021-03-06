from __future__ import absolute_import

import operator
import os
import os.path
import sys
import warnings

import six

from enstaller.collections import DefaultOrderedDict
from enstaller.eggcollect import info_from_metadir
from enstaller.errors import NoSuchPackage
from enstaller.package import (InstalledPackageMetadata,
                               RemotePackageMetadata)
from enstaller.utils import PY_VER
from enstaller.versions import EnpkgVersion


def _valid_meta_dir_iterator(prefixes):
    for prefix in prefixes:
        egg_info_root = os.path.join(prefix, "EGG-INFO")
        if os.path.isdir(egg_info_root):
            for path in os.listdir(egg_info_root):
                meta_dir = os.path.join(egg_info_root, path)
                yield prefix, egg_info_root, meta_dir


class Repository(object):
    """
    A Repository is a set of package, and knows about which package it
    contains.
    """
    def _populate_from_prefixes(self, prefixes):
        if prefixes is None:  # pragma: nocover
            prefixes = [sys.prefix]

        prefix_info = []
        json_dict = {}
        for prefix, egg_info_root, meta_dir in _valid_meta_dir_iterator(prefixes):
            info = info_from_metadir(meta_dir)
            if info is not None:
                prefix_info.append((prefix, info))
                json_dict[info["key"]] = info

        requirement_normalizer = _RequirementNormalizer(json_dict)

        for prefix, info in prefix_info:
            key = info["key"]
            info = requirement_normalizer(key, info)

            package = InstalledPackageMetadata.from_installed_meta_dict(
                info, prefix
            )
            self.add_package(package)

    @classmethod
    def _from_prefixes(cls, prefixes=None):
        """
        Create a repository representing the *installed* packages.

        Parameters
        ----------
        prefixes: seq
            List of prefixes. [sys.prefix] by default
        """
        repository = cls()
        repository._populate_from_prefixes(prefixes)
        return repository

    @classmethod
    def from_repository_infos(cls, session, repository_infos):
        """ Create a repository from a remote index.

        Parameters
        ----------
        session : Session
            A session instance (must be authenticated)
        repository_infos : iterable
            Iterable of IRepositoryInfo instances, containing the metadata for
            the repository to fetch.

        Note
        ----
        This is a convenience ctor, which is useful in scripting. It is
        inefficient as it fetch repository info's indices serially. Use the
        parse_index function with your favorite concurrency framework (threads,
        futures, etc...) if you want better IO performances.
        """
        repository = cls()

        for repository_info in repository_infos:
            resp = session.fetch(repository_info.index_url)
            json_data = resp.json()

            for package in parse_index(json_data, repository_info):
                repository.add_package(package)

        return repository

    def __init__(self, packages=None):
        self._name_to_packages = DefaultOrderedDict(list)

        self._store_info = ""

        packages = packages or []
        for package in packages:
            self.add_package(package)

    def __len__(self):
        return sum(len(self._name_to_packages[p])
                   for p in self._name_to_packages)

    def __iter__(self):
        return self.iter_packages()

    def add_package(self, package_metadata):
        self._name_to_packages[package_metadata.name].append(package_metadata)
        # Fixme: this should not be that costly as long as we don't have
        # many versions for a given package.
        self._name_to_packages[package_metadata.name].sort(
            key=operator.attrgetter("version")
        )

    def delete_package(self, package_metadata):
        """ Remove the given package.

        Removing a non-existent package is an error.

        Parameters
        ----------
        package_metadata : PackageMetadata
            The package to remove
        """
        if not self.has_package(package_metadata):
            msg = "Package '{0}-{1}' not found".format(
                package_metadata.name, package_metadata.version)
            raise NoSuchPackage(msg)
        else:
            candidates = [p for p in
                          self._name_to_packages[package_metadata.name]
                          if p.full_version != package_metadata.full_version]
            self._name_to_packages[package_metadata.name] = candidates

    def has_package(self, package_metadata):
        """Returns True if the given package is available in this repository

        Parameters
        ----------
        package_metadata : PackageMetadata
            The package to look for.

        Returns
        -------
        ret : bool
            True if the package is in the repository, false otherwise.
        """
        candidates = self._name_to_packages[package_metadata.name]
        for candidate in candidates:
            if candidate.full_version == package_metadata.full_version:
                return True
        return False

    def find_package(self, name, version):
        """Search for the first match of a package with the given name and
        version.

        Parameters
        ----------
        name : str
            The package name to look for.
        version : str
            The full version string to look for (e.g. '1.8.0-1').

        Returns
        -------
        package : RemotePackageMetadata
            The corresponding metadata.
        """
        version = EnpkgVersion.from_string(version)
        candidates = self._name_to_packages[name]
        for candidate in candidates:
            if candidate.version == version:
                return candidate
        raise NoSuchPackage("Package '{0}-{1}' not found".format(name,
                                                                 version))

    def find_package_from_requirement(self, requirement):
        """Search for latest package matching the given requirement.

        Parameters
        ----------
        requirement : Requirement
            The requirement to match for.

        Returns
        -------
        package : RemotePackageMetadata
            The corresponding metadata.
        """
        candidates = [
            candidate for candidate in self.find_packages(requirement.name)
            if requirement.matches(candidate.version)
        ]

        if len(candidates) == 0:
            msg = "No package found for requirement {0!r}"
            raise NoSuchPackage(msg.format(requirement))

        candidates.sort(key=operator.attrgetter("version"))
        return candidates[-1]

    def find_latest_package(self, name):
        """Returns the latest package with the given name.

        Parameters
        ----------
        name : str
            The package's name

        Returns
        -------
        package : PackageMetadata
        """
        packages = self.find_packages(name)
        if len(packages) < 1:
            raise NoSuchPackage("No package with name {0!r}".format(name))
        else:
            return packages[-1]

    def find_sorted_packages(self, name):
        """ Returns a list of package metadata with the given name and version,
        sorted from lowest to highest version.

        Parameters
        ----------
        name : str
            The package's name
        version : str or None
            If not None, the version to look for

        Returns
        -------
        packages : iterable
            Iterable of RemotePackageMetadata-like (order is unspecified)

        .. deprecated:: 4.9
           Use :method:`find_packages`.
        """
        msg = ("find_sorted_packages is deprecated: find_packages is "
               "now guaranteed to return the list of packages sorted by "
               "version.")
        warnings.warn(msg, DeprecationWarning)
        return self.find_packages(name)

    def find_packages(self, name, version=None):
        """ Returns a list of package metadata with the given name and version,
        sorted from lowest to highest version.

        Parameters
        ----------
        name : str
            The package's name
        version : str or None
            If not None, the version to look for

        Returns
        -------
        packages : iterable
            Iterable of RemotePackageMetadata-like (order is unspecified)
        """
        candidates = self._name_to_packages.get(name, [])
        if version is None:
            return [package for package in candidates]
        else:
            return [package for package in candidates if package.full_version == version]

    def iter_packages(self):
        """Iter over each package of the repository

        Returns
        -------
        packages : iterable
            Iterable of RemotePackageMetadata-like.
        """
        for packages_set in self._name_to_packages.values():
            for package in packages_set:
                yield package

    def iter_most_recent_packages(self):
        """Iter over each package of the repository, but only the most recent
        version of a given package

        Returns
        -------
        packages : iterable
            Iterable of the corresponding RemotePackageMetadata-like
            instances.
        """
        for name, packages in self._name_to_packages.items():
            yield packages[-1]

    def update(self, repository):
        """ Add the given repository's packages to this repository.
        """
        for package in repository:
            self.add_package(package)


def parse_index(json_dict, repository_info, python_version=PY_VER):
    """
    Parse the given json index data and iterate package instance over its
    content.

    Parameters
    ----------
    json_dict: dict
        Parsed legacy json index
    repository_info: IRepositoryInfo
        An object describing the remote repository to parse
    python_version: str
        The major.minor string describing the python version. This generator
        will iterate over every package where the python attribute is `null` or
        equal to this string. If python_version == "*", then every package is
        iterated over.
    """
    # We cache versions as building instances of EnpkgVersion from a string is
    # slow. For the PyPi repository, caching saves ~90 % of the calls, and
    # speed up parse_index by ~300 ms on my machine.
    cache = {}

    def _version_factory(upstream, build):
        if (upstream, build) in cache:
            version = cache[(upstream, build)]
        else:
            version = EnpkgVersion.from_upstream_and_build(upstream, build)
            cache[(upstream, build)] = version
        return version

    requirement_normalizer = _RequirementNormalizer(json_dict)

    for key, info in six.iteritems(json_dict):
        info.setdefault('type', 'egg')
        info.setdefault('packages', [])
        info.setdefault('python', python_version)

        version = _version_factory(info["version"], info["build"])
        info = requirement_normalizer(key, info)

        if python_version == "*" or info["python"] in (None, python_version):
            yield RemotePackageMetadata.from_json_dict_and_version(
                key, info, version, repository_info
            )


class _RequirementNormalizer(object):
    """ Normalize name/requirement names in our legacy index

    For some reason, for each entry in our index, the name is always lower
    case, but the requirement may be upper-case (e.g. MKL or Cython). To avoid
    pushing this complexity down to the dependency solver, we normalize
    requirement names to match names, e.g. is the package name is `mkl`, then a
    requirement like `MKL 10.3` will be converted to `mkl 10.3`.
    """
    def __init__(self, json_data):
        egg_name_to_name = {}
        for key, value in six.iteritems(json_data):
            egg_name = key.split("-", 1)[0]
            egg_name_to_name[egg_name] = value["name"]

        self._egg_name_to_name = egg_name_to_name

    def _normalizer(self, requirement_name):
        return self._egg_name_to_name.get(
            requirement_name, requirement_name.lower()
        )

    def _normalize_value(self, key, value):
        egg_name = key.split("-", 1)[0]
        if "packages" in value:
            value["packages"] = _normalize_requirement_names(
                value["packages"], self._normalizer
            )
        return value

    def __call__(self, key, value):
        return self._normalize_value(key, value)


def _normalize_requirement_names(requirements, normalizer):
    def _normalize_requirement_name(requirement):
        parts = requirement.split(None, 1)
        if len(parts) > 0:
            parts[0] = normalizer(parts[0])
        return " ".join(parts)

    return [
        _normalize_requirement_name(requirement)
        for requirement in requirements
    ]
