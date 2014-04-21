import collections
import os.path

from okonomiyaki.repositories.enpkg import EnpkgS3IndexEntry

from enstaller.store.base import AbstractStore


class DumbFilesystemStore(AbstractStore):
    def __init__(self, root, eggs, product_type=None):
        self.root = root

        self._index = {}
        for egg in eggs:
            path = os.path.join(root, egg)
            metadata = EnpkgS3IndexEntry.from_egg(path, product_type, True)
            self._index[metadata.s3index_key] = metadata

        self._name_to_keys = collections.defaultdict(list)
        for key, info in self._index.iteritems():
            self._name_to_keys[info.name].append(key)

    def connect(self, authentication):
        pass

    def is_connected(self):
        return True

    def info(self):
        return {"root": self.root}

    def _query_keys(self, **kwargs):
        name = kwargs.get('name')
        if name is None:
            for key, info in self._index.items():
                if all(getattr(info, k) == v for k, v in kwargs.items()):
                    yield key
        else:
            del kwargs['name']
            for key in self._name_to_keys[name]:
                info = self._index[key]
                if all(getattr(info, k) == v for k, v in kwargs.items()):
                    yield key

    def query(self, **kwargs):
        for key in self._query_keys(**kwargs):
            yield key, self._index[key].s3index_data

    def exists(self, key):
        return key in self._index

    def get(self, key):
        return self.get_data(key), self.get_metadata(key)

    def get_data(self, key):
        if key in self._index:
            path = os.path.join(self.root, key)
            return open(path, "rb")
        else:
            raise KeyError("No such key: {0!r}".format(key))

    def get_metadata(self, key):
        return self._index[key].s3index_data
