import abc
import posixpath

import enstaller.plat

from egginst._compat import with_metaclass
from egginst.vendor.six.moves import urllib

from enstaller.auth import _INDEX_NAME


class IRepositoryInfo(with_metaclass(abc.ABCMeta)):
    @abc.abstractproperty
    def index_url(self):
        """ The exact url to fetch the index at."""

    @abc.abstractproperty
    def name(self):
        """ An arbitrary string identifying the repository."""

    @abc.abstractproperty
    def _base_url(self):
        """ Kept for backward compatibility, to be removed once we can depend
        on brood."""

    @abc.abstractmethod
    def _package_url(self, package):
        """ The exact url to fetch the given package at.

        Parameters
        ----------
        package : PackageMetadata
            the package metadata
        """

    @abc.abstractproperty
    def _key(self):
        """ Tuple containing the data used for hashing the object."""

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        else:
            return self._key == other._key

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self._key)


class ILegacyRepositoryInfo(IRepositoryInfo):
    pass


class CanopyRepositoryInfo(ILegacyRepositoryInfo):
    def __init__(self, store_url, use_pypi=False, platform=None):
        self._platform = platform or enstaller.plat.custom_plat
        self._store_url = store_url
        self._use_pypi = use_pypi
        self._path = "/eggs/{0._platform}".format(self)

    @property
    def _key(self):
        return (self._platform, self._store_url, self._use_pypi)

    @property
    def index_url(self):
        url = urllib.parse.urljoin(self._store_url, self._path + "/" + _INDEX_NAME)
        if self._use_pypi:
            url += "?pypi=true"
        else:
            url += "?pypi=false"
        return url

    @property
    def name(self):
        parts = urllib.parse.urlsplit(self._store_url)
        return urllib.parse.urlunsplit(("canopy+https", parts[1], "", "", ""))

    @property
    def _base_url(self):
        return urllib.parse.urljoin(self._store_url, self._path + "/")

    def _package_url(self, package):
        return urllib.parse.urljoin(self._store_url,
                                    self._path + "/" + package.key)


class OldstyleRepositoryInfo(ILegacyRepositoryInfo):
    def __init__(self, store_url):
        self._store_url = store_url

    @property
    def index_url(self):
        return urllib.parse.urljoin(self._store_url, _INDEX_NAME)

    @property
    def name(self):
        parts = urllib.parse.urlsplit(self._store_url)
        return urllib.parse.urlunsplit(("", "", parts[2], parts[3], parts[4]))

    @property
    def _base_url(self):
        return self._store_url

    @property
    def _key(self):
        return (self._store_url, )

    def _package_url(self, package):
        return urllib.parse.urljoin(self._store_url, package.key)


class IBroodRepositoryInfo(IRepositoryInfo):
    pass


class BroodRepositoryInfo(IBroodRepositoryInfo):
    def __init__(self, store_url, name, platform=None):
        self._platform = platform or enstaller.plat.custom_plat
        self._name = name
        self._store_url = store_url

        self._path = "/repo/{0._name}/{0._platform}".format(self)

    @property
    def index_url(self):
        return urllib.parse.urljoin(self._store_url, self._path + "/" + _INDEX_NAME)

    @property
    def name(self):
        return self._name

    @property
    def _base_url(self):
        return urllib.parse.urljoin(self._store_url, self._path + "/")

    @property
    def _key(self):
        return (self._name, self._platform, self._store_url)

    def _package_url(self, package):
        return urllib.parse.urljoin(self._store_url, self._path + "/" + package.key)

    def __repr__(self):
        return "BroodRepository(<{0._store_url}>, <{0.name}>)".format(self)


class FSRepositoryInfo(IBroodRepositoryInfo):
    def __init__(self, store_url):
        self._store_url = store_url

    @property
    def index_url(self):
        return posixpath.join(self._store_url, _INDEX_NAME)

    @property
    def name(self):
        return self._store_url

    @property
    def _base_url(self):
        return self._store_url

    @property
    def _key(self):
        return (self._store_url,)

    def _package_url(self, package):
        return posixpath.join(self._store_url, package.key)

    def __repr__(self):
        return "FSRepositoryInfo(<{0}>)".format(self._store_url)
