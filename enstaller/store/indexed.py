import json
import urlparse
import urllib2
from collections import defaultdict

from enstaller.errors import EnstallerException, InvalidConfiguration

from base import AbstractStore
from cached import CachedHandler
from compressed import CompressedHandler


_INDEX_NAME = "index.json"


class IndexedStore(AbstractStore):

    def __init__(self):
        super(IndexedStore, self).__init__()
        self._connected = False

    def _is_key_index(self, key):
        return key.startswith(_INDEX_NAME)

    def connect(self, userpass=None):
        self.userpass = userpass  # tuple(username, password)

        self._index = self.get_index()
        self._connected = True

        for info in self._index.itervalues():
            info['store_location'] = self.info().get('root')
            info.setdefault('type', 'egg')
            info.setdefault('python', '2.7')
            info.setdefault('packages', [])

        # maps names to keys
        self._groups = defaultdict(list)
        for key, info in self._index.iteritems():
            self._groups[info['name']].append(key)

    @property
    def is_connected(self):
        return self._connected

    def get_index(self):
        fp = self.get_data(_INDEX_NAME)
        return json.load(fp)

    def _location(self, key):
        rt = self.root.rstrip('/') + '/'
        if key.endswith('.zdiff'):
            return rt + 'patches/' + key
        return rt + key

    def get(self, key):
        return self.get_data(key), self.get_metadata(key)

    def get_metadata(self, key):
        return self._index[key]

    def exists(self, key):
        return key in self._index

    def query(self, **kwargs):
        for key in self.query_keys(**kwargs):
            yield key, self._index[key]

    def query_keys(self, **kwargs):
        name = kwargs.get('name')
        if name is None:
            for key, info in self._index.iteritems():
                if all(info.get(k) == v for k, v in kwargs.iteritems()):
                    yield key
        else:
            del kwargs['name']
            for key in self._groups[name]:
                info = self._index[key]
                if all(info.get(k) == v for k, v in kwargs.iteritems()):
                    yield key


class LocalIndexedStore(IndexedStore):

    def __init__(self, root_dir):
        super(LocalIndexedStore, self).__init__()
        self.root = root_dir


    def info(self):
        return dict(root=self.root)

    def get_data(self, key):
        try:
            return open(self._location(key), 'rb')
        except IOError as e:
            # FIXME: this is moronic, but hard to fix nicely until we get rid
            # of the terrible store API.
            if self._is_key_index(key):
                msg = "Could not access the index file for local repository {0!r}"
                raise InvalidConfiguration(msg.format(self._location(key)))
            else:
                raise KeyError(str(e))


class RemoteHTTPIndexedStore(IndexedStore):
    @classmethod
    def from_configuration(cls, config):
        return cls(config.webservice_entry_point, config.local,
                   config.use_pypi)

    def __init__(self, url, cache_dir, use_pypi=True):
        super(RemoteHTTPIndexedStore, self).__init__()

        self.root = url
        self.cache_dir = cache_dir
        self._use_pypi = use_pypi

    def info(self):
        return dict(root=self.root)

    def get_index(self):
        if self._use_pypi is True:
            url = '{0}?pypi=true'.format(_INDEX_NAME)
        else:
            url = '{0}?pypi=false'.format(_INDEX_NAME)

        fp = self.get_data(url)
        return json.load(fp)

    def get_data(self, key):
        url = self._location(key)
        scheme, netloc, path, params, query, frag = urlparse.urlparse(url)
        auth, host = urllib2.splituser(netloc)
        if auth:
            auth = urllib2.unquote(auth)
        elif self.userpass:
            auth = ('%s:%s' % self.userpass)

        if auth:
            new_url = urlparse.urlunparse((scheme, host, path,
                                           params, query, frag))
            request = urllib2.Request(new_url)
            request.add_unredirected_header("Authorization",
                                "Basic " + auth.encode('base64').strip())
        else:
            request = urllib2.Request(url)
        request.add_header('User-Agent', 'enstaller')
        try:
            return self.opener.open(request)
        except urllib2.HTTPError as e:
            # FIXME: this is moronic, but hard to fix nicely until we get rid
            # of the terrible store API.
            if self._is_key_index(key):
                if e.code == 404:
                    msg = "Could not access the index file for repository {0!r}"
                    raise EnstallerException(msg.format(self._location(key)))
                else:
                    raise
            else:
                if e.code == 404:
                    raise KeyError("%s: %s" % (e, url))
                else:
                    raise
        except urllib2.URLError as e:
            raise Exception("Could not connect to %s (reason: %s / %s)" % (host, e.reason, e.args))

    @property
    def opener(self):
        """ Create custom urlopener with Compression and Caching handlers. """
        # Use handlers from urllib2's default opener, since we already
        # added our proxy handler to it.
        opener = urllib2._opener
        http_handlers = [urllib2.HTTPHandler, urllib2.HTTPSHandler]
        handlers = opener.handlers if opener is not None else http_handlers

        # Add our handlers to the default handlers.
        handlers_ = [CompressedHandler, CachedHandler(self.cache_dir)] + handlers

        return urllib2.build_opener(*handlers_)
