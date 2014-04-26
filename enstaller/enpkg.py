from __future__ import print_function

import contextlib
import logging
import operator
import os
import threading
import sys
import tempfile

from uuid import uuid4
from os.path import isdir, isfile, join

import enstaller

from enstaller.errors import EnpkgError
from enstaller.repository import Repository, egg_name_to_name_version
from enstaller.store.indexed import LocalIndexedStore, RemoteHTTPIndexedStore
from enstaller.store.joined import JoinedStore

from enstaller.eggcollect import EggCollection, JoinedEggCollection

from enstaller.resolve import Req, Resolve
from enstaller.fetch import FetchAPI
from enstaller.egg_meta import split_eggname
from enstaller.history import History

from enstaller.config import Configuration


logger = logging.getLogger(__name__)


def create_joined_store(config, urls):
    stores = []
    for url in urls:
        if url.startswith('file://'):
            stores.append(LocalIndexedStore(url[7:]))
        elif url.startswith(('http://', 'https://')):
            stores.append(RemoteHTTPIndexedStore(url, config.local))
        elif isdir(url):
            stores.append(LocalIndexedStore(url))
        else:
            raise Exception("cannot create store: %r" % url)
    return JoinedStore(stores)


def get_default_kvs(config):
    url = config.webservice_entry_point
    return RemoteHTTPIndexedStore(url, config.local)


def get_writable_local_dir(config):
    local_dir = config.repository_cache
    if not os.access(local_dir, os.F_OK):
        try:
            os.makedirs(local_dir)
            return local_dir
        except (OSError, IOError):
            pass
    elif os.access(local_dir, os.W_OK):
        return local_dir

    logger.warn('Warning: Python prefix directory is not writeable '
           'with current permissions:\n'
           '    %s\n'
           'Using a temporary cache for index and eggs.\n' %
           config.prefix)
    return tempfile.mkdtemp()


def get_default_remote(config):
    url = config.webservice_entry_point
    local_dir = get_writable_local_dir(config)
    return RemoteHTTPIndexedStore(url, local_dir, config.use_pypi)


class Enpkg(object):
    """
    This is main interface for using enpkg, it is used by the CLI.
    Arguments for object creation:

    remote: key-value store (KVS) instance
        This is the KVS which enpkg will try to connect to for querying
        and fetching eggs.

    All remaining arguments are optional.

    userpass: tuple(username, password) -- default, see below
        these credentials are used when the remote KVS instance is being
        connected.
        By default the credentials are obtained from config.get_auth(),
        which might use the keyring package.

    prefixes: list of path -- default: [sys.prefix]
        Each path, is an install "prefix" (such as, e.g. /usr/local)
        in which things get installed.
        Eggs are installed or removed from the first prefix in the list.

    evt_mgr: encore event manager instance -- default: None
        Various progress events (e.g. for download, install, ...) are being
        emitted to the event manager.  By default, a simple progress bar
        is displayed on the console (which does not use the event manager
        at all).
    """
    def __init__(self, remote=None, userpass='<config>', prefixes=[sys.prefix],
                 hook=False, evt_mgr=None, config=None):
        if config is None:
            self.config = Configuration._get_default_config()
        else:
            self.config = config

        self.local_dir = get_writable_local_dir(self.config)
        if remote is None:
            remote = get_default_remote(self.config)
        self._repository = Repository(remote)

        # XXX: remote attribute kept for backward compatibility, remove before
        # 4.7.0
        self.remote = remote

        if userpass == '<config>':
            self.userpass = self.config.get_auth()
        else:
            self.userpass = userpass

        self.prefixes = prefixes
        self.evt_mgr = evt_mgr

        if hook is not False:
            raise EnpkgError("hook feature has been removed")
        self.ec = JoinedEggCollection([
                EggCollection(prefix, self.evt_mgr)
                for prefix in self.prefixes])
        self._execution_aborted = threading.Event()

    # ============= methods which relate to remove store =================

    def reconnect(self):
        """
        Normally it is not necessary to call this method, it is only there
        to offer a convenient way to (re)connect the key-value store.
        This is necessary to update to changes which have occured in the
        store, as the remote store might create a cache during connecting.
        """
        self._connect(force=True)

    def _connect(self, force=False):
        self._repository.connect(self.userpass)

    def find_remote_packages(self, name):
        """
        Find every package with the given name on the configured remote
        repository(ies)

        Returns
        -------
        packages: seq
            List of RepositoryPackageMetadata instances
        """
        # FIXME: we should connect in one place consistently
        self._repository.connect(self.userpass)
        return self._repository.find_packages(name)

    def remote_packages(self):
        """
        Iter over every remote package

        Returns
        -------
        it: iterator
            Iterate over (key, RepositoryPackageMetadata) pairs
        """
        # FIXME: we should connect in one place consistently
        self._repository.connect(self.userpass)
        return self._repository.iter_packages()

    def info_list_name(self, name):
        """
        return (sorted by versions (when possible)), a list of metadata
        dictionaries which are available on the remote KVS for a given name
        """
        req = Req(name)
        info_list = []
        for package_metadata in self._repository.find_packages(name):
            if req.matches(package_metadata.s3index_data):
                info_list.append(package_metadata)
        try:
            return sorted(info_list, key=operator.attrgetter("comparable_version"))
        except TypeError:
            return info_list

    # ============= methods which relate to local installation ===========
    def installed_packages(self):
        """
        Iter over each installed package

        Returns
        -------
        it: iterator
            Iterator over (key, package info dict) pairs.
        """
        return self.ec.query()

    def find_installed_packages(self, name):
        """
        Query installed packages.  In addition to the remote metadata the
        following attributes are added:

        ctime: creation (install) time (string representing local time)

        installed: True (always)

        meta_dir: the path to the egg metadata directory on the local system
        """
        return self.ec.query(name=name)

    def find(self, egg):
        """
        Return the local egg metadata (see ``query_installed``) for a given
        egg (key) or None is the egg is not installed
        """
        return self.ec.find(egg)

    def _execute_opcode(self, opcode, egg):
        logger.info('\t' + str((opcode, egg)))
        if opcode.startswith('fetch_'):
            self.fetch(egg, force=int(opcode[-1]))
        elif opcode == 'remove':
            self.ec.remove(egg)
        elif opcode == 'install':
            name, version = egg_name_to_name_version(egg)
            if self._repository.is_connected:
                package = self._repository.find_package(name, version)
                extra_info = package.s3index_data
            else:
                extra_info = None
            self.ec.install(egg, self.local_dir, extra_info)
        else:
            raise Exception("unknown opcode: %r" % opcode)

    @contextlib.contextmanager
    def _enpkg_progress_manager(self, actions):
        if self.evt_mgr:
            from encore.events.api import ProgressManager
            progress = ProgressManager(
                    self.evt_mgr, source=self,
                    operation_id=self.super_id,
                    message="super",
                    steps=len(actions))

        else:
            def _fake_progress(step=0):
                pass
            progress = _fake_progress

        self.super_id = None
        for c in self.ec.collections:
            c.super_id = self.super_id

        try:
            yield progress
        finally:
            self.super_id = uuid4()
            for c in self.ec.collections:
                c.super_id = self.super_id

    def execute(self, actions):
        """
        Execute actions, which is an iterable over tuples(action, egg_name),
        where action is one of 'fetch', 'remote', or 'install' and egg_name
        is the filename of the egg.
        This method is only meant to be called with actions created by the
        *_actions methods below.
        """
        logger.info("Enpkg.execute: %d", len(actions))

        with History(self.prefixes[0]):
            with self._enpkg_progress_manager(actions) as progress:
                for n, (opcode, egg) in enumerate(actions):
                    if self._execution_aborted.is_set():
                        self._execution_aborted.clear()
                        break
                    self._execute_opcode(opcode, egg)
                    progress(step=n)

    def abort_execution(self):
        self._execution_aborted.set()

    def _install_actions_enstaller(self, installed_version=None):
        # installed_version is only useful for testing
        if installed_version is None:
            installed_version = enstaller.__version__

        mode = 'recur'
        self._connect()
        req = Req.from_anything("enstaller")
        eggs = Resolve(self._repository).install_sequence(req, mode)
        if eggs is None:
            raise EnpkgError("No egg found for requirement '%s'." % req)
        elif not len(eggs) == 1:
            raise EnpkgError("No egg found to update enstaller, aborting...")
        else:
            name, version, build = split_eggname(eggs[0])
            if version == installed_version:
                return []
            else:
                return self._install_actions(eggs, mode, False, False)

    def install_actions(self, arg, mode='recur', force=False, forceall=False):
        """
        Create a list of actions which are required for installing, which
        includes updating, a package (without actually doing anything).

        The first argument may be any of:
          * the KVS key, i.e. the egg filename
          * a requirement object (enstaller.resolve.Req)
          * the requirement as a string
        """
        req = Req.from_anything(arg)
        # resolve the list of eggs that need to be installed
        self._connect()
        eggs = Resolve(self._repository).install_sequence(req, mode)
        if eggs is None:
             raise EnpkgError("No egg found for requirement '%s'." % req)
        return self._install_actions(eggs, mode, force, forceall)

    def _install_actions(self, eggs, mode, force, forceall):
        if not forceall:
            # remove already installed eggs from egg list
            if force:
                eggs = self._filter_installed_eggs(eggs[:-1]) + [eggs[-1]]
            else:
                eggs = self._filter_installed_eggs(eggs)

        res = []
        for egg in eggs:
            res.append(('fetch_%d' % bool(forceall or force), egg))

        # remove packages with the same name (from first egg collection
        # only, in reverse install order)
        for egg in reversed(eggs):
            name = split_eggname(egg)[0].lower()
            index = dict(self.ec.collections[0].query(name=name))
            assert len(index) < 2
            if len(index) == 1:
                res.append(('remove', index.keys()[0]))
        for egg in eggs:
            res.append(('install', egg))
        return res

    def _filter_installed_eggs(self, eggs):
        """ Filter out already installed eggs from the given egg list.

        Note that only visible eggs are filtered.
        For example, if in multiple prefixes, a lower prefix has an egg
        which is overridden by a different version in a higher prefix,
        then only the top-most egg is considered and the egg in lower prefix
        is not considered.
        """
        filtered_eggs = []
        for egg in eggs:
            for installed in self.ec.query(name=split_eggname(egg)[0].lower()):
                if installed[0] == egg:
                    break
            else:
                filtered_eggs.append(egg)
        return filtered_eggs

    def remove_actions(self, arg):
        """
        Create the action necessary to remove an egg.  The argument, may be
        one of ..., see above.
        """
        req = Req.from_anything(arg)
        assert req.name
        index = dict(self.ec.collections[0].query(**req.as_dict()))
        if len(index) == 0:
            raise EnpkgError("package %s not installed in: %r" %
                             (req, self.prefixes[0]))
        return [('remove', index.keys()[0])]

    def revert_actions(self, arg):
        """
        Calculate the actions necessary to revert to a given state, the
        argument may be one of:
          * complete set of eggs, i.e. a set of egg file names
          * revision number (negative numbers allowed)
        """
        h = History(self.prefixes[0])
        h.update()
        if isinstance(arg, set):
            state = arg
        else:
            try:
                rev = int(arg)
            except (TypeError, ValueError):
                raise EnpkgError("Invalid argument: integer expected, "
                                 "got: {0!r}".format(arg))
            try:
                state = h.get_state(rev)
            except IndexError:
                raise EnpkgError("Error: no such revision: %r" % arg)

        curr = h.get_state()
        if state == curr:
            return []

        res = []
        for egg in curr - state:
            if egg.startswith('enstaller'):
                continue
            res.append(('remove', egg))

        for egg in state - curr:
            if egg.startswith('enstaller'):
                continue
            if not isfile(join(self.local_dir, egg)):
                self._repository.connect(self.userpass)
                if self._repository._has_package_key(egg):
                    res.append(('fetch_0', egg))
                else:
                    raise EnpkgError("cannot revert -- missing %r" % egg)
            res.append(('install', egg))
        return res

    def get_history(self):
        """
        return a history (h) object with this Enpkg instance prefix.
        """
        # FIXME: only used by canopy
        return History(self.prefixes[0])

    # == methods which relate to both (remote store and local installation) ==

    def find_packages(self, name):
        """
        Iter over each package with the given name

        Parameters
        ----------
        name: str
            The package name (e.g. 'numpy')

        Returns
        -------
        it: generator
            A generator over (key, package info dict) pairs
        """
        index = dict((package.key, package.s3index_data) for package in
                     self.find_remote_packages(name))
        for key, info in self.find_installed_packages(name):
            if key in index:
                index[key].update(info)
            else:
                index[key] = info
        for k in index:
            yield k, index[k]

    def fetch(self, egg, force=False):
        self._connect()
        f = FetchAPI(self._repository, self.local_dir, self.evt_mgr)
        f.super_id = getattr(self, 'super_id', None)
        f.fetch_egg(egg, force, self._execution_aborted)
