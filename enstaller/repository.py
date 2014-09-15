import collections
import operator
import os
import os.path
import sys
import urllib
import urlparse

from egginst.eggmeta import info_from_z
from egginst._zipfile import ZipFile

from enstaller.errors import EnstallerException, MissingPackage
from enstaller.eggcollect import info_from_metadir
from enstaller.utils import comparable_version, compute_md5


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
        return cls(key, json_dict["name"], json_dict["version"],
                   json_dict["build"], json_dict["packages"],
                   json_dict["python"])

    def __init__(self, key, name, version, build, packages, python):
        self.key = key

        self.name = name
        self.version = version
        self.build = build

        self.packages = packages
        self.python = python

    def __repr__(self):
        return "PackageMetadata('{0}-{1}-{2}', key={3!r})".format(
            self.name, self.version, self.build, self.key)

    @property
    def full_version(self):
        """
        The full version as a string (e.g. '1.8.0-1' for the numpy-1.8.0-1.egg)
        """
        return "{0}-{1}".format(self.version, self.build)

    @property
    def comparable_version(self):
        """
        Returns an object that may be used to compare the version of two
        package metadata (only make sense for two packages which differ only in
        versions).
        """
        return comparable_version(self.version), self.build

    @property
    def _spec_info(self):
        """
        Returns a dictionary that can be used as an argument to Req.matches
        """
        # FIXME: to remove before 4.7.0
        keys = ("name", "python", "version", "build")
        return dict((k, getattr(self, k)) for k in keys)

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
            store_location = urllib.pathname2url(os.path.dirname(path)) + "/"
            store_location = urlparse.urljoin("file:/", store_location)

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
        return cls(key, json_dict["name"], json_dict["version"],
                   json_dict["build"], json_dict["packages"],
                   json_dict["python"], json_dict["size"], json_dict["md5"],
                   json_dict.get("mtime", 0.0), json_dict.get("product", None),
                   json_dict.get("available", True),
                   json_dict["store_location"])

    def __init__(self, key, name, version, build, packages, python, size, md5,
                 mtime, product, available, store_location):
        super(RepositoryPackageMetadata, self).__init__(key, name, version,
                                                        build, packages,
                                                        python)

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
        keys = ("available", "build", "md5", "name", "packages", "product",
                "python", "mtime", "size", "type", "version")
        return dict((k, getattr(self, k)) for k in keys)

    @property
    def source_url(self):
        return urlparse.urljoin(self.store_location, self.key)

    def __repr__(self):
        template = "RepositoryPackageMetadata(" \
            "'{self.name}-{self.version}-{self.build}', key={self.key!r}, " \
            "available={self.available!r}, product={self.product!r}, " \
            "store_location={self.store_location!r})".format(self=self)
        return template.format(self.name, self.version, self.build, self.key,
                               self.available, self.product,
                               self.store_location)


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
        return cls(json_dict["key"], json_dict["name"], json_dict["version"],
                   json_dict["build"], json_dict.get("packages", []),
                   json_dict["python"], json_dict["ctime"],
                   json_dict.get("store_location", ""))

    def __init__(self, key, name, version, build, packages, python, ctime,
                 store_location):
        super(InstalledPackageMetadata, self).__init__(key, name, version,
                                                       build, packages, python)

        self.ctime = ctime
        self.store_location = store_location

    @property
    def _compat_dict(self):
        """
        Returns a dict that is used in some old APIs
        """
        # FIXME: this method is to be removed
        keys = ("name", "name", "version", "build", "packages", "python",
                "ctime")
        return dict((k, getattr(self, k)) for k in keys)

def parse_version(version):
    """
    Parse a full version (e.g. '1.8.0-1' into upstream and build)

    Parameters
    ----------
    version: str

    Returns
    -------
    upstream_version: str
    build: int
    """
    parts = version.split("-")
    if len(parts) != 2:
        raise ValueError("Version not understood {0!r}".format(version))
    else:
        return parts[0], int(parts[1])

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
        if prefixes is None: #  pragma: nocover
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

    def __init__(self, store_info=""):
        self._name_to_packages = collections.defaultdict(list)

        self._store_info = ""

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
            raise MissingPackage(msg)
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
        candidates = self._name_to_packages.get(name, [])
        for candidate in candidates:
            if candidate.full_version == version:
                return candidate
        raise MissingPackage("Package '{0}-{1}' not found".format(name,
                                                                  version))


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
                          key=operator.attrgetter("comparable_version"))
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
        for packages_set in self._name_to_packages.itervalues():
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
                                       key=operator.attrgetter("comparable_version"))
            yield sorted_by_version[-1]
