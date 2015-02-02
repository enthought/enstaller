import collections
import operator
import os
import os.path
import sys

from enstaller.eggcollect import info_from_metadir
from enstaller.errors import NoSuchPackage
from enstaller.package import (InstalledPackageMetadata,
                               RemotePackageMetadata)
from enstaller.utils import PY_VER
from enstaller.versions.pep386_workaround import PEP386WorkaroundVersion
from enstaller.versions.enpkg import EnpkgVersion


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

        for prefix, egg_info_root, meta_dir in _valid_meta_dir_iterator(prefixes):
            info = info_from_metadir(meta_dir)
            if info is not None:
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
    def from_repository_info(cls, session, repository_info):
        """ Create a repository from a remote index.

        Parameters
        ----------
        session : Session
            A session instance (must be authenticated)
        repository_info : IRepositoryInfo
            The metadata for the repository to fetch.
        """
        repository = cls()

        resp = session.fetch(repository_info.index_url)
        json_data = resp.json()

        for package in parse_index(json_data, repository_info):
            repository.add_package(package)
        return repository

    def __init__(self, packages=None):
        self._name_to_packages = collections.defaultdict(list)

        self._store_info = ""

        packages = packages or []
        for package in packages:
            self.add_package(package)

    def __len__(self):
        return sum(len(self._name_to_packages[p])
                   for p in self._name_to_packages)

    def add_package(self, package_metadata):
        self._name_to_packages[package_metadata.name].append(package_metadata)

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
        candidates = self._name_to_packages.get(package_metadata.name, [])
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
        candidates = self._name_to_packages.get(name, [])
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
        name = requirement.name
        version = requirement.version
        build = requirement.build
        if version is None:
            return self.find_latest_package(name)
        else:
            if build is None:
                upstream = PEP386WorkaroundVersion.from_string(version)
                candidates = [p for p in self.find_packages(name)
                              if p.version.upstream == upstream]
                candidates.sort(key=operator.attrgetter("version"))

                if len(candidates) == 0:
                    msg = "No package found for requirement {0!r}"
                    raise NoSuchPackage(msg.format(requirement))

                return candidates[-1]
            else:
                version = EnpkgVersion.from_upstream_and_build(version, build)
                return self.find_package(name, str(version))

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
        packages = self.find_sorted_packages(name)
        if len(packages) < 1:
            raise NoSuchPackage("No package with name {0!r}".format(name))
        else:
            return packages[-1]

    def find_sorted_packages(self, name):
        """Returns a list of package metadata with the given name and version,
        sorted from lowest to highest version (when possible).

        Parameters
        ----------
        name : str
            The package's name

        Returns
        -------
        packages : iterable
            Iterable of RemotePackageMetadata.
        """
        packages = self.find_packages(name)
        try:
            return sorted(packages,
                          key=operator.attrgetter("version"))
        except TypeError:
            # FIXME: allowing uncomparable versions should be disallowed at
            # some point
            return packages

    def find_packages(self, name, version=None):
        """ Returns a list of package metadata with the given name and version

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
            sorted_by_version = sorted(packages,
                                       key=operator.attrgetter("version"))
            yield sorted_by_version[-1]


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

    for key, info in json_dict.items():
        info.setdefault('type', 'egg')
        info.setdefault('packages', [])
        info.setdefault('python', python_version)

        version = _version_factory(info["version"], info["build"])
        if python_version == "*" or info["python"] in (None, python_version):
            yield RemotePackageMetadata.from_json_dict_and_version(
                key, info, version, repository_info
            )
