import os
import json
import string
from os.path import isdir, isfile, join
from abc import ABCMeta, abstractmethod

import egginst

from egg_meta import split_eggname


class AbstractEggCollection(object):

    __metaclass__ = ABCMeta

    @abstractmethod
    def find(self, egg):
        """Look for the given egg in this collection.

        Parameters
        ----------
        egg: str
            The egg filename

        Returns
        -------
        Egg dict info if found, None otherwise.
        """

    @abstractmethod
    def query(self, **kwargs):
        """Iterate (name, info) pairs for each egg satisfying the given query
        in this collection.
        """

    @abstractmethod
    def install(self, egg, dir_path):
        """Install the given egg from the given directory

        Parameters
        ----------
        egg: str
            Egg filename
        dir_path: str
            Directory where to look for the egg
        """

    @abstractmethod
    def remove(self, egg):
        """Remove the given egg

        Parameters
        ----------
        egg: str
            Egg filename
        """


def info_from_metadir(meta_dir):
    path = join(meta_dir, '_info.json')
    if isfile(path):
        try:
            info = json.load(open(path))
        except ValueError:
            return None
        info['installed'] = True
        info['meta_dir'] = meta_dir
        return info
    return None


class EggCollection(AbstractEggCollection):

    def __init__(self, prefix, evt_mgr=None):
        self.prefix = prefix
        self.evt_mgr = evt_mgr
        self.verbose = False

        self.pkgs_dir = join(self.prefix, 'pkgs')

    def find(self, egg):
        try:
            n, v, b = split_eggname(egg)
        except AssertionError:
            return None
        path = join(self.prefix, 'EGG-INFO', n.lower())
        info = info_from_metadir(path)
        if info and info['key'] == egg:
            return info
        else:
            return None

    def query(self, **kwargs):
        name = kwargs.get('name')
        egginfo_dir = join(self.prefix, 'EGG-INFO')
        if not isdir(egginfo_dir):
            return
        for fn in sorted(os.listdir(egginfo_dir), key=string.lower):
            if name and fn != name:
                continue
            info = info_from_metadir(join(egginfo_dir, fn))
            if info and all(info.get(k) == v
                            for k, v in kwargs.iteritems()):
                yield info['key'], info

    def install(self, egg, dir_path, extra_info=None):
        ei = egginst.EggInst(join(dir_path, egg),
                             prefix=self.prefix,
                             evt_mgr=self.evt_mgr,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.super_id = getattr(self, 'super_id', None)
        ei.install(extra_info)

    def remove(self, egg):
        ei = egginst.EggInst(egg,
                             prefix=self.prefix,
                             evt_mgr=self.evt_mgr,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.super_id = getattr(self, 'super_id', None)
        ei.remove()


class JoinedEggCollection(AbstractEggCollection):

    def __init__(self, collections):
        self.collections = collections

    def find(self, egg):
        for collection in self.collections:
            info = collection.find(egg)
            if info:
                return info
        return None

    def query(self, **kwargs):
        # Use the package name as the dict-key so that eggs in a collection of
        # higher precedence overwrites those in collection of lower precedence.
        index_by_name = {}
        for collection in reversed(self.collections):
            for key, info in collection.query(**kwargs):
                index_by_name[info['name']] = info
        # Switch keys to the egg name.
        index_iter = ((info['key'], info)
                      for name, info in index_by_name.iteritems())
        return index_iter

    def install(self, egg, dir_path, extra_info=None):
        self.collections[0].install(egg, dir_path, extra_info)

    def remove(self, egg):
        self.collections[0].remove(egg)
