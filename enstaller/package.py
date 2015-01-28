import os.path
import time

from egginst.eggmeta import info_from_z
from egginst._zipfile import ZipFile

from enstaller.egg_meta import split_eggname
from enstaller.eggcollect import info_from_metadir
from enstaller.errors import EnstallerException
from enstaller.repository_info import FSRepositoryInfo
from enstaller.utils import compute_md5, path_to_uri, PY_VER
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

        self._dependencies = frozenset(packages)
        self.python = python

    def __repr__(self):
        return "PackageMetadata('{0}-{1}', key={2!r})".format(
            self.name, self.version, self.key)

    @property
    def _egg_name(self):
        return split_eggname(self.key)[0]

    @property
    def _comp_key(self):
        return (self.name, self.version, self._dependencies, self.python)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        else:
            return self._comp_key == other._comp_key

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self._comp_key)

    @property
    def dependencies(self):
        return self._dependencies

    @property
    def packages(self):
        # FIXME: we keep packages for backward compatibility (called as is in
        # the index).
        return list(self._dependencies)

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
    def from_egg(cls, path, repository_info=None):
        """
        Create an instance from an egg filename.
        """
        with ZipFile(path) as zp:
            metadata = info_from_z(zp)

        repository_info = repository_info or \
            FSRepositoryInfo(path_to_uri(os.path.dirname(path)))

        metadata["packages"] = metadata.get("packages", [])
        st = os.stat(path)
        metadata["size"] = st.st_size
        metadata["md5"] = compute_md5(path)
        metadata["mtime"] = st.st_mtime
        return cls.from_json_dict(os.path.basename(path), metadata,
                                  repository_info)

    @classmethod
    def from_json_dict(cls, key, json_dict, repository_info):
        version = EnpkgVersion.from_upstream_and_build(json_dict["version"],
                                                       json_dict["build"])
        return cls(key, json_dict["name"], version, json_dict["packages"],
                   json_dict["python"], json_dict["size"], json_dict["md5"],
                   json_dict.get("mtime", 0.0), json_dict.get("product", None),
                   json_dict.get("available", True),
                   repository_info)

    def __init__(self, key, name, version, packages, python, size, md5,
                 mtime, product, available, repository_info):
        super(RepositoryPackageMetadata, self).__init__(key, name, version,
                                                        packages, python)

        self.size = size
        self.md5 = md5

        self.mtime = mtime
        self.product = product
        self.available = available
        self.repository_info = repository_info

        self.type = "egg"

    @property
    def _comp_key(self):
        return (super(RepositoryPackageMetadata, self)._comp_key +
                (self.size, self.md5, self.mtime, self.product, self.available,
                 self.repository_info, self.type))

    @property
    def s3index_data(self):
        """
        Returns a dict that may be converted to json to re-create our legacy S3
        index content
        """
        keys = ("available", "md5", "name", "product",
                "python", "mtime", "size", "type")
        ret = dict((k, getattr(self, k)) for k in keys)
        ret["version"] = str(self.version.upstream)
        ret["build"] = self.version.build
        ret["packages"] = list(self.packages)
        return ret

    @property
    def source_url(self):
        return self.repository_info._package_url(self)

    def __repr__(self):
        template = "RepositoryPackageMetadata(" \
            "'{self.name}-{self.version}', key={self.key!r}, " \
            "available={self.available!r}, product={self.product!r}, " \
            "repository_info='{self.repository_info!r}')".format(self=self)
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

    @property
    def _comp_key(self):
        return (super(InstalledPackageMetadata, self)._comp_key +
                (self.ctime, self.store_location))


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
