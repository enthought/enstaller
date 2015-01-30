import os.path
import sys
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
        self._key = key

        self._name = name
        self._version = version

        self._dependencies = frozenset(packages)
        self._python = python

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
    def full_version(self):
        """
        The full version as a string (e.g. '1.8.0-1' for the numpy-1.8.0-1.egg)
        """
        return str(self.version)

    @property
    def name(self):
        return self._name

    @property
    def key(self):
        return self._key

    @property
    def packages(self):
        # FIXME: we keep packages for backward compatibility (called as is in
        # the index).
        return list(self._dependencies)

    @property
    def python(self):
        return self._python

    @property
    def version(self):
        return self._version


class RepositoryPackageMetadata(PackageMetadata):
    """
    RepositoryPackageMetadata encompasses the full set of package metadata
    available from a repository.

    In particular, RepositoryPackageMetadata's instances know about which
    repository they are coming from through the repository_info attribute.
    """
    @classmethod
    def from_egg(cls, path, repository_info=None, python_version=PY_VER):
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

        self._size = size
        self._md5 = md5

        self._mtime = mtime
        self._product = product
        self._available = available
        self._repository_info = repository_info

    @property
    def _comp_key(self):
        return (super(RepositoryPackageMetadata, self)._comp_key +
                (self.size, self.md5, self.mtime, self.product, self.available,
                 self.repository_info))

    @property
    def available(self):
        return self._available

    @property
    def md5(self):
        return self._md5

    @property
    def mtime(self):
        return self._mtime

    @property
    def product(self):
        return self._product

    @property
    def repository_info(self):
        return self._repository_info

    @property
    def size(self):
        return self._size

    @property
    def s3index_data(self):
        """
        Returns a dict that may be converted to json to re-create our legacy S3
        index content
        """
        keys = ("available", "md5", "name", "product",
                "python", "mtime", "size")
        ret = dict((k, getattr(self, k)) for k in keys)
        ret["version"] = str(self.version.upstream)
        ret["build"] = self.version.build
        ret["packages"] = list(self.packages)
        ret["type"] = "egg"
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
    def from_egg(cls, path, ctime, prefix=None):
        """
        Create an instance from an egg filename.
        """
        prefix = prefix or sys.prefix

        with ZipFile(path) as zp:
            metadata = info_from_z(zp)
        metadata["packages"] = metadata.get("packages", [])
        metadata["ctime"] = ctime
        metadata["key"] = os.path.basename(path)
        return cls.from_installed_meta_dict(metadata, prefix)

    @classmethod
    def from_meta_dir(cls, meta_dir, prefix=None):
        meta_dict = info_from_metadir(meta_dir)
        if meta_dict is None:
            message = "No installed metadata found in {0!r}".format(meta_dir)
            raise EnstallerException(message)
        else:
            prefix = prefix or sys.prefix
            return cls.from_installed_meta_dict(meta_dict, prefix)

    @classmethod
    def from_installed_meta_dict(cls, json_dict, prefix=None):
        prefix = prefix or sys.prefix

        key = json_dict["key"]
        name = json_dict["name"]
        upstream_version = json_dict["version"]
        build = json_dict.get("build", 1)
        version = EnpkgVersion.from_upstream_and_build(upstream_version, build)
        packages = json_dict.get("packages", [])
        python = json_dict.get("python", PY_VER)
        ctime = json_dict.get("ctime", time.ctime(0.0))
        return cls(key, name, version, packages, python, ctime, prefix)

    def __init__(self, key, name, version, packages, python, ctime,
                 prefix):
        super(InstalledPackageMetadata, self).__init__(key, name, version,
                                                       packages, python)

        self._ctime = ctime
        self._prefix = prefix

    @property
    def ctime(self):
        return self._ctime

    @property
    def prefix(self):
        return self._prefix

    @property
    def _comp_key(self):
        return (super(InstalledPackageMetadata, self)._comp_key +
                (self.ctime, self._prefix))


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
