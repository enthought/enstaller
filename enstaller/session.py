import collections
import contextlib
import os.path
import threading

from egginst.utils import atomic_file, ensure_dir
from egginst.vendor.six.moves import urllib

from enstaller import __version__
from enstaller.auth.auth_managers import (BroodAuthenticator,
                                          LegacyCanopyAuthManager,
                                          OldRepoAuthManager)
from enstaller.config import STORE_KIND_BROOD
from enstaller.errors import EnstallerException
from enstaller.vendor import requests
from enstaller.vendor.cachecontrol.adapter import CacheControlAdapter

from enstaller.requests_utils import (DBCache, LocalFileAdapter,
                                      QueryPathOnlyCacheController)

from enstaller.auth import UserPasswordAuth


class _PatchedRawSession(requests.Session):
    """ Like requests.Session, but supporting (nested) umounting of
    adapters.
    """
    def __init__(self, *a, **kw):
        self._adapters_stack = collections.defaultdict(list)
        super(_PatchedRawSession, self).__init__(*a, **kw)

    def mount(self, prefix, adapter):
        self._adapters_stack[prefix].append(adapter)
        super(_PatchedRawSession, self).mount(prefix, adapter)

    def umount(self, prefix):
        if prefix in self._adapters_stack \
                and len(self._adapters_stack[prefix]) > 0:
            self.adapters.pop(prefix)
            current_adapter = self._adapters_stack[prefix].pop()

            if len(self._adapters_stack[prefix]) > 0:
                previous_adapter = self._adapters_stack[prefix][-1]
                self.adapters[prefix] = previous_adapter

            return current_adapter
        else:
            msg = "no adapter registered for prefix {0!r}".format(prefix)
            raise ValueError(msg)


class Session(object):
    """ Simple class to handle http session management

    It also ensures connection settings such as proxy, SSL CA certification,
    etc... are handled consistently).

    Parameters
    ----------
    authenticator : IAuthManager
        An authenticator instance
    cache_directory : str
        A writeable directory to cache data and eggs.
    proxies : dict
        A proxy dict as expected by requests (and provided by
        Configuration.proxy_dict).
    verify : bool
        If True, SSL CA are verified (default).
    """
    def __init__(self, authenticator, cache_directory, proxies=None,
                 verify=True, max_retries=0):
        self.proxies = proxies
        self.verify = verify
        self.cache_directory = cache_directory
        self.max_retries = max_retries

        self._authenticator = authenticator
        self._raw = _PatchedRawSession()
        if proxies is not None:
            self._raw.proxies = proxies
        self._raw.verify = verify

        self._raw.mount("file://", LocalFileAdapter())

        adapter = requests.adapters.HTTPAdapter(max_retries=self.max_retries)
        for prefix in ("http://", "https://"):
            self._raw.mount(prefix, adapter)

        user_agent = "enstaller/{0} {1}".format(__version__,
                                                self._raw.headers["user-agent"])
        self._raw.headers["user-agent"] = user_agent

        self._in_etag_context = 0
        self._etag_context_lock = threading.RLock()

    @classmethod
    def authenticated_from_configuration(cls, configuration):
        """ Create a new authenticated session from a configuration.

        Parameters
        ----------
        configuration : Configuration
            The configuration to use.
        """
        if configuration.auth is None:
            msg = "No auth configured for the given configuration."
            raise EnstallerException(msg)
        session = cls.from_configuration(configuration)
        session.authenticate(configuration.auth)
        return session

    @classmethod
    def from_configuration(cls, configuration):
        """ Create a new session from a configuration.

        Parameters
        ----------
        configuration : Configuration
            The configuration to use.
        """
        if configuration.store_kind == STORE_KIND_BROOD:
            klass = BroodAuthenticator
        elif configuration.use_webservice:
            klass = LegacyCanopyAuthManager
        else:
            klass = OldRepoAuthManager
        authenticator = klass.from_configuration(configuration)
        return cls(authenticator, configuration.repository_cache,
                   configuration.proxy_dict, verify=configuration.verify_ssl,
                   max_retries=configuration.max_retries)

    def close(self):
        self._raw.close()

    def __enter__(self):
        return self

    def __exit__(self, *a, **kw):
        self.close()

    @contextlib.contextmanager
    def etag(self):
        with self._etag_context_lock:
            self._etag_setup()
        try:
            yield
        finally:
            with self._etag_context_lock:
                self._etag_tear()

    def _etag_setup(self):
        if self._in_etag_context == 0:
            uri = os.path.join(self.cache_directory, "index_cache", "index.db")
            ensure_dir(uri)
            cache = DBCache(uri)

            for prefix in ("http://", "https://"):
                adapter = CacheControlAdapter(
                    cache, controller_class=QueryPathOnlyCacheController,
                    max_retries=self.max_retries)
                self._raw.mount(prefix, adapter)

        self._in_etag_context += 1

    def _etag_tear(self):
        if self._in_etag_context == 1:
            for prefix in ("https://", "http://"):
                # XXX: This close is ugly, but I am not sure how one can link a cache
                # controller to a http adapter in cachecontrol. See issue #42 on
                # ionrock/cachecontrol @ github.
                adapter = self._raw.umount(prefix)
                adapter.cache.close()
        self._in_etag_context -= 1

    def authenticate(self, auth):
        if isinstance(auth, tuple) and len(auth) == 2:
            auth = UserPasswordAuth(auth[0], auth[1])

        self._authenticator.authenticate(self, auth.request_adapter)
        self._raw.auth = self._authenticator._auth

    def download(self, url, target=None):
        """ Safely download the content at the give url.

        Safely here is understood as not leaving stalled content if the
        download fails or is canceled. It uses streaming as so not to use too
        much memory.
        """
        resp = self._raw.get(url, stream=True)
        resp.raise_for_status()

        if target is None:
            target = os.path.basename(urllib.parse.urlparse(url).path)

        with atomic_file(target) as fp:
            for chunk in resp.iter_content(1024):
                fp.write(chunk)

        return target

    def fetch(self, url):
        resp = self._raw.get(url, stream=True)
        resp.raise_for_status()
        return resp

    def get(self, url, stream=False):
        return self._raw.get(url, stream=stream)

    def head(self, url):
        return self._raw.head(url)

    def _raw_get(self, url, auth=None):
        return self._raw.get(url, auth=auth)

    def _raw_head(self, url, auth=None):
        return self._raw.head(url, auth=auth)

    def _raw_post(self, url, auth=None):
        return self._raw.post(url, auth=auth)
