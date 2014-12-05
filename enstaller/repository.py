import collections
import operator
import os
import os.path
import sys
import time

from egginst.eggmeta import info_from_z
from egginst.vendor.six.moves import urllib
from egginst._zipfile import ZipFile

from enstaller.errors import EnstallerException, NoSuchPackage
from enstaller.eggcollect import info_from_metadir
from enstaller.utils import compute_md5, path_to_uri, PY_VER
from enstaller.versions.pep386_workaround import PEP386WorkaroundVersion
from enstaller.versions.enpkg import EnpkgVersion


class PackageVersionInfo(object):
    def __init__(self, name, version):
        self.name = name
        self.version = version


class PackageMetadata(object):
    """
    PackageMetadataBase encompasses the metadata required to resolve
    dependencies.

    They are not attached to a repository.
    """
    @classmethod
    def from_egg(cls, path):
        """
        Create an instance from an egg filename.
        """
        with ZipFile(path) as zp:
            metadata = info_from_z(zp)
        metadata["packages"] = metadata.get("packages", [])
        return cls.from_json_dict(os.path.basename(path), metadata)

    @classmethod
    def from_json_dict(cls, key, json_dict):
        """
        Create an instance from a key (the egg filename) and metadata passed as
        a dictionary
        """
        version = EnpkgVersion.from_upstream_and_build(json_dict["version"],
                                                       json_dict["build"])
        return cls(key, json_dict["name"], version, json_dict["packages"],
                   json_dict["python"])

    def __init__(self, key, name, version, packages, python):
        self.key = key

        self.name = name
        self.version = version

        self.packages = packages
        self.python = python

    def __repr__(self):
        return "PackageMetadata('{0}-{1}', key={2!r})".format(
            self.name, self.version, self.key)

    @property
    def dependencies(self):
        # FIXME: we keep packages for backward compatibility (called as is in
        # the index).
        return self.packages

    @property
    def full_version(self):
        """
        The full version as a string (e.g. '1.8.0-1' for the numpy-1.8.0-1.egg)
        """
        return str(self.version)


class RepositoryPackageMetadata(PackageMetadata):
    """
    RepositoryPackageMetadata encompasses the full set of package metadata
    available from a repository.

    In particular, RepositoryPackageMetadata's instances know about which
    repository they are coming from through the store_location attribute.
    """
    @classmethod
    def from_egg(cls, path, store_location=""):
        """
        Create an instance from an egg filename.
        """
        with ZipFile(path) as zp:
            metadata = info_from_z(zp)

        if len(store_location) == 0:
            store_location = path_to_uri(os.path.dirname(path)) + "/"

        if not store_location.endswith("/"):
            msg = "Invalid uri for store location: {0!r} (expected an uri " \
                  "ending with '/')".format(store_location)
            raise ValueError(msg)

        metadata["packages"] = metadata.get("packages", [])
        st = os.stat(path)
        metadata["size"] = st.st_size
        metadata["md5"] = compute_md5(path)
        metadata["mtime"] = st.st_mtime
        metadata["store_location"] = store_location
        return cls.from_json_dict(os.path.basename(path), metadata)

    @classmethod
    def from_json_dict(cls, key, json_dict):
        version = EnpkgVersion.from_upstream_and_build(json_dict["version"],
                                                       json_dict["build"])
        return cls(key, json_dict["name"], version, json_dict["packages"],
                   json_dict["python"], json_dict["size"], json_dict["md5"],
                   json_dict.get("mtime", 0.0), json_dict.get("product", None),
                   json_dict.get("available", True),
                   json_dict["store_location"])

    def __init__(self, key, name, version, packages, python, size, md5,
                 mtime, product, available, store_location):
        super(RepositoryPackageMetadata, self).__init__(key, name, version,
                                                        packages, python)

        self.size = size
        self.md5 = md5

        self.mtime = mtime
        self.product = product
        self.available = available
        self.store_location = store_location

        self.type = "egg"

    @property
    def s3index_data(self):
        """
        Returns a dict that may be converted to json to re-create our legacy S3
        index content
        """
        keys = ("available", "md5", "name", "packages", "product",
                "python", "mtime", "size", "type")
        ret = dict((k, getattr(self, k)) for k in keys)
        ret["version"] = str(self.version.upstream)
        ret["build"] = self.version.build
        return ret

    @property
    def source_url(self):
        return urllib.parse.urljoin(self.store_location, self.key)

    def __repr__(self):
        template = "RepositoryPackageMetadata(" \
            "'{self.name}-{self.version}', key={self.key!r}, " \
            "available={self.available!r}, product={self.product!r}, " \
            "store_location={self.store_location!r})".format(self=self)
        return template


class InstalledPackageMetadata(PackageMetadata):
    @classmethod
    def from_egg(cls, path, ctime, store_location):
        """
        Create an instance from an egg filename.
        """
        with ZipFile(path) as zp:
            metadata = info_from_z(zp)
        metadata["packages"] = metadata.get("packages", [])
        metadata["ctime"] = ctime
        metadata["store_location"] = store_location
        metadata["key"] = os.path.basename(path)
        return cls.from_installed_meta_dict(metadata)

    @classmethod
    def from_meta_dir(cls, meta_dir):
        meta_dict = info_from_metadir(meta_dir)
        if meta_dict is None:
            message = "No installed metadata found in {0!r}".format(meta_dir)
            raise EnstallerException(message)
        else:
            return cls.from_installed_meta_dict(meta_dict)

    @classmethod
    def from_installed_meta_dict(cls, json_dict):
        key = json_dict["key"]
        name = json_dict["name"]
        upstream_version = json_dict["version"]
        build = json_dict.get("build", 1)
        version = EnpkgVersion.from_upstream_and_build(upstream_version, build)
        packages = json_dict.get("packages", [])
        python = json_dict.get("python", PY_VER)
        ctime = json_dict.get("ctime", time.ctime(0.0))
        store_location = json_dict.get("store_location", "")
        return cls(key, name, version, packages, python, ctime,
                   store_location)

    def __init__(self, key, name, version, packages, python, ctime,
                 store_location):
        super(InstalledPackageMetadata, self).__init__(key, name, version,
                                                       packages, python)

        self.ctime = ctime
        self.store_location = store_location


def egg_name_to_name_version(egg_name):
    """
    Convert a eggname (filename) to a (name, version) pair.

    Parameters
    ----------
    egg_name: str
        The egg filename

    Returns
    -------
    name: str
        The name
    version: str
        The *full* version (e.g. for 'numpy-1.8.0-1.egg', the full version is
        '1.8.0-1')
    """
    basename = os.path.splitext(os.path.basename(egg_name))[0]
    parts = basename.split("-", 1)
    if len(parts) != 2:
        raise ValueError("Invalid egg name: {0!r}".format(egg_name))
    else:
        return parts[0].lower(), parts[1]


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
                info["store_location"] = prefix

                package = \
                    InstalledPackageMetadata.from_installed_meta_dict(info)
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
        package : RepositoryPackageMetadata
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
        package : RepositoryPackageMetadata
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
            Iterable of RepositoryPackageMetadata.
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
            Iterable of RepositoryPackageMetadata-like (order is unspecified)
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
            Iterable of RepositoryPackageMetadata-like.
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
            Iterable of the corresponding RepositoryPackageMetadata-like
            instances.
        """
        for name, packages in self._name_to_packages.items():
            sorted_by_version = sorted(packages,
                                       key=operator.attrgetter("version"))
            yield sorted_by_version[-1]
