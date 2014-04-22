import collections
import os
import os.path
import textwrap

from egginst.eggmeta import info_from_z
from egginst.utils import ZipFile, compute_md5


from enstaller.errors import MissingPackage
from enstaller.fetch import StoreResponse
from enstaller.utils import comparable_version


class PackageMetadata(object):
    @classmethod
    def from_egg(cls, path):
        with ZipFile(path) as zp:
            metadata = info_from_z(zp)
        st = os.stat(path)
        metadata["size"] = st.st_size
        metadata["md5"] = compute_md5(path)
        metadata["packages"] = metadata.get("packages", [])
        return cls.from_json_dict(os.path.basename(path), metadata)

    @classmethod
    def from_json_dict(cls, key, json_dict):
        return cls(key, json_dict["name"], json_dict["version"],
                   json_dict["build"], json_dict["packages"],
                   json_dict["python"], json_dict["size"], json_dict["md5"])

    def __init__(self, key, name, version, build, packages, python, size, md5):
        self.key = key

        self.name = name
        self.version = version
        self.build = build

        self.packages = packages
        self.python = python

        self.size = size
        self.md5 = md5

    def __repr__(self):
        return "PackageMetadata('{0}-{1}-{2}', key='{3}')".format(
            self.name, self.version, self.build, self.key)

    @property
    def comparable_version(self):
        return comparable_version(self.version), self.build


class RepositoryPackageMetadata(object):
    @classmethod
    def from_json_dict(cls, key, json_dict):
        return cls(key, json_dict["name"], json_dict["version"],
                   json_dict["build"], json_dict["packages"],
                   json_dict["python"], json_dict["size"], json_dict["md5"],
                   json_dict.get("product", None), json_dict.get("available", True),
                   json_dict["store_location"])

    def __init__(self, key, name, version, build, packages, python, size, md5,
                 product, available, store_location):
        self._package = PackageMetadata(key, name, version, build, packages, python, size, md5)

        self.product = product
        self.available = available
        self.store_location = store_location

        self.type = "egg"

    def to_dict(self):
        keys = ("available", "build", "md5", "name", "packages", "product",
                "python", "size", "type", "version")
        return dict((k, getattr(self, k)) for k in keys)

    def __repr__(self):
        template = textwrap.dedent("""\
            RepositoryPackageMetadata('{0}-{1}-{2}', key={3!r}',
                                      available={4!r}, product={!5r},
                                      product={!6r})
        """)
        return template.format(self.name, self.version, self.build, self.key,
                               self.available, self.product,
                               self.store_location)

    @property
    def comparable_version(self):
        return self._package.comparable_version

    # FIXME: would be nice to have some basic delegate functionalities instead
    @property
    def key(self):
        return self._package.key

    @property
    def name(self):
        return self._package.name

    @property
    def version(self):
        return self._package.version

    @property
    def build(self):
        return self._package.build

    @property
    def packages(self):
        return self._package.packages

    @property
    def python(self):
        return self._package.python

    @property
    def md5(self):
        return self._package.md5

    @property
    def size(self):
        return self._package.size


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

class Repository(object):
    def __init__(self, store):
        self._store = store
        store_info = self._store.info()
        self._store_info = store_info.get("root") if store_info else ""

    def _package_metadata_from_key(self, key):
        data = self._store.get_metadata(key)
        data["store_location"] =  self._store_info
        return RepositoryPackageMetadata.from_json_dict(key, data)

    @property
    def is_connected(self):
        return self._store.is_connected

    def connect(self, auth):
        if not self._store.is_connected:
            self._store.connect(auth)

    # FIXME: this should be removed at some point, as this is too low-level
    def _has_package_key(self, key):
        """
        Returns True if the given package is available in this repository
        """
        return self._store.exists(key)

    def has_package(self, package_metadata):
        """
        Returns True if the given package is available in this repository
        """
        return self._store.exists(package_metadata.key)

    def find_package(self, name, version):
        """ Search for the first match of a package with the given name and
        version.

        Returns
        -------
        package: RepositoryPackageMetadata
            The corresponding metadata
        """
        upstream_version, build = parse_version(version)
        keys = list(self._store.query_keys(type="egg", name=name, version=upstream_version))
        if len(keys) < 1:
            raise MissingPackage("Package '{0}-{1}' not found".format(name, version))
        else:
            key = keys[0]
            return self._package_metadata_from_key(key)

    def find_packages(self, name, version=None):
        """
        Returns a list of package metadata with the given name and version

        Parameters
        ----------
        name: str
            The package's name
        version: str or None
            If not None, the version to look for

        Returns
        -------
        packages: seq of RepositoryPackageMetadata
            The corresponding metadata (order is unspecified)
        """
        kw = {"name": name, "type": "egg"}
        if version is not None:
            upstream_version, build = parse_version(version)
            kw["version"] = upstream_version
            kw["build"] = build

        return [self._package_metadata_from_key(key)
                for key in self._store.query_keys(**kw)]

    def iter_packages(self):
        """
        Iter over each package of the repository

        Returns
        -------
        packages: iterable of RepositoryPackageMetadata
            The corresponding metadata
        """
        for key in self._store.query_keys(type="egg"):
            yield self._package_metadata_from_key(key)

    def iter_most_recent_packages(self):
        """
        Iter over each package of the repository, but only the most recent
        version of a given package

        Returns
        -------
        packages: iterable of RepositoryPackageMetadata
            The corresponding metadata
        """
        package_name_to_keys = collections.defaultdict(list)
        for key in self._store.query_keys(type="egg"):
            metadata = self._store.get_metadata(key)
            name = metadata["name"]
            version = metadata["version"]
            package_name_to_keys[name].append((version, key))

        def keyfunc(pair):
            return comparable_version(pair[0])

        for name, version_pairs in package_name_to_keys.items():
            sorted_by_version = sorted(version_pairs, key=keyfunc)
            latest_pair = sorted_by_version[-1]
            latest_key = latest_pair[1]
            yield self._package_metadata_from_key(latest_key)

    def fetch_from_package(self, package_metadata):
        return StoreResponse(self._store.get_data(package_metadata.key),
                             package_metadata.size)
