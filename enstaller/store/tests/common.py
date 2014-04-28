import collections
import os
import os.path

from okonomiyaki.repositories.enpkg import EnpkgS3IndexEntry

from enstaller.store.indexed import LocalIndexedStore
from enstaller.utils import PY_VER

class MetadataOnlyStore(LocalIndexedStore):
    """
    A simple store implementation which may be used when only metadata are
    needed in tests.
    """
    def __init__(self, entries=None):
        if entries is None:
            entries = []
        super(MetadataOnlyStore, self).__init__("")
        self._entries = entries

    def connect(self, auth=None):
        self._index = self.get_index()
        self._groups = collections.defaultdict(list)

        for entry in self._entries:
            self._groups[entry.name].append(entry.s3index_key)

    def get_index(self):
        return dict((entry.s3index_key, entry.s3index_data) for entry in self._entries)

class EggsStore(LocalIndexedStore):
    """
    A simple store implementation which may be used when actual eggs are needed
    in tests.
    """
    def __init__(self, eggs):
        super(EggsStore, self).__init__("")

        self._entries = [EnpkgS3IndexEntry.from_egg(egg, available=True) for egg in eggs]
        # XXX: hack to use same eggs on all supported versions
        for entry in self._entries:
            entry.python = PY_VER
        self._eggs = dict((os.path.basename(egg), egg) for egg in eggs)

    def connect(self, auth=None):
        self._index = self.get_index()
        self._groups = collections.defaultdict(list)

        for entry in self._entries:
            self._groups[entry.name].append(entry.s3index_key)

    def get_index(self):
        return dict((entry.s3index_key, entry.s3index_data) for entry in self._entries)

    def get_data(self, key):
        return open(self._eggs[key], "rb")
