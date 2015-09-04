import abc
import posixpath

from okonomiyaki.file_formats import PythonImplementation

import enstaller.plat

from egginst._compat import with_metaclass
from egginst._compat import urljoin, urlsplit, urlunsplit

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
        url = urljoin(self._store_url, self._path + "/" + _INDEX_NAME)
        if self._use_pypi:
            url += "?pypi=true"
        else:
            url += "?pypi=false"
        return url

    @property
    def name(self):
        parts = urlsplit(self._store_url)
        return urlunsplit(("canopy+https", parts[1], "", "", ""))

    @property
    def _base_url(self):
        return urljoin(self._store_url, self._path + "/")

    def _package_url(self, package):
        return urljoin(self._store_url, self._path + "/" + package.key)


class OldstyleRepositoryInfo(ILegacyRepositoryInfo):
    def __init__(self, store_url):
        self._store_url = store_url

    @property
    def index_url(self):
        return urljoin(self._store_url, _INDEX_NAME)

    @property
    def name(self):
        parts = urlsplit(self._store_url)
        return urlunsplit(("", "", parts[2], parts[3], parts[4]))

    @property
    def _base_url(self):
        return self._store_url

    @property
    def _key(self):
        return (self._store_url, )

    def _package_url(self, package):
        return urljoin(self._store_url, package.key)


class IBroodRepositoryInfo(IRepositoryInfo):
    pass


class BroodRepositoryInfo(IBroodRepositoryInfo):
    def __init__(self, store_url, name, platform=None, python_tag=None):
        self._platform = platform or enstaller.plat.custom_plat
        self._python_tag = (
            python_tag or
            PythonImplementation.from_running_python().pep425_tag
        )
        self._name = name
        self._store_url = store_url

        self._path = ("/api/v0/json/indices/{0._name}/{0._platform}/"
                      "{0._python_tag}/eggs".format(self))

    def update(self, platform=None, python_tag=None):
        return BroodRepositoryInfo(
            self._store_url, self._name, platform, python_tag
        )

    @property
    def index_url(self):
        return urljoin(self._store_url, self._path)

    @property
    def name(self):
        return self._name

    @property
    def _base_url(self):
        raise NotImplementedError()

    @property
    def _key(self):
        return (self._name, self._platform, self._store_url)

    def _package_url(self, package):
        # FIXME: as soon as we can rely solely on brood, use `python_tag`
        # attribute from each package instead of this hack (#552)
        if package.python is None:
            python_tag = 'none'
        else:
            parts = package.python.split(".")
            assert len(parts) == 2
            python_tag = "cp" + parts[0] + parts[1]
        path = ("/api/v0/json/data/{0._name}/{0._platform}/{1}"
                "/eggs/{2.name}/{2.version}".format(self, python_tag, package))
        return urljoin(self._store_url, path)

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
