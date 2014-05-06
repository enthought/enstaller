from __future__ import print_function

import contextlib
import logging
import os
import threading
import sys
import tempfile

from uuid import uuid4
from os.path import isfile, join

from egginst.main import EggInst
from egginst.progress import progress_manager_factory

import enstaller

from enstaller.errors import EnpkgError, UnavailablePackage
from enstaller.eggcollect import meta_dir_from_prefix
from enstaller.repository import (InstalledPackageMetadata, Repository,
                                  egg_name_to_name_version)

from enstaller.resolve import Req, Resolve
from enstaller.egg_meta import split_eggname
from enstaller.history import History

from enstaller.config import Configuration


logger = logging.getLogger(__name__)


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


class _ExecuteContext(object):
    def __init__(self, prefix, actions):
        self._actions = actions
        self._prefix = prefix

    @property
    def n_actions(self):
        return len(self._actions)

    def iter_actions(self):
        with History(self._prefix):
            for action in self._actions:
                yield action


class Enpkg(object):
    """ This is main interface for using enpkg, it is used by the CLI.
    Arguments for object creation:

    Parameters
    ----------
    repository: Repository
        This is the remote repository which enpkg will use to resolve
        dependencies.
    prefixes: list of path -- default: [sys.prefix]
        Each path, is an install "prefix" (such as, e.g. /usr/local) in which
        things get installed. Eggs are installed or removed from the first
        prefix in the list.
    evt_mgr: encore event manager instance -- default: None
        Various progress events (e.g. for download, install, ...) are being
        emitted to the event manager.  By default, a simple progress bar is
        displayed on the console (which does not use the event manager at all).
    """
    def __init__(self, remote_repository, download_manager,
                 prefixes=[sys.prefix], evt_mgr=None, config=None):
        if config is None:
            self.config = Configuration._get_default_config()
        else:
            self.config = config

        self.local_dir = get_writable_local_dir(self.config)

        self.prefixes = prefixes
        self.top_prefix = prefixes[0]

        self.evt_mgr = evt_mgr

        self._remote_repository = remote_repository

        self._installed_repository = Repository._from_prefixes(self.prefixes)
        self._top_installed_repository = Repository._from_prefixes([self.top_prefix])

        self._execution_aborted = threading.Event()

        self._downloader = download_manager

    def _install_egg(self, path, extra_info=None):
        """
        Install the given egg.

        Parameters
        ----------
        path: str
            The path to the egg to install
        """
        name, _ = egg_name_to_name_version(path)

        installer = EggInst(path, prefix=self.prefixes[0], evt_mgr=self.evt_mgr)
        installer.super_id = getattr(self, 'super_id', None)
        installer.install(extra_info)

        meta_dir = meta_dir_from_prefix(self.top_prefix, name)
        package = InstalledPackageMetadata.from_meta_dir(meta_dir)

        self._top_installed_repository.add_package(package)
        self._installed_repository.add_package(package)

    def _remove_egg(self, egg):
        """
        Remove the given egg.

        Parameters
        ----------
        path: str
            The egg basename (e.g. 'numpy-1.8.0-1.egg')
        """
        remover = EggInst(egg, prefix=self.top_prefix)
        remover.super_id = getattr(self, 'super_id', None)
        remover.remove()

        # FIXME: we recalculate the full repository because we don't have a
        # feature to remove a package yet
        self._top_installed_repository = \
            Repository._from_prefixes([self.prefixes[0]])

    def _execute_opcode(self, opcode, egg):
        logger.info('\t' + str((opcode, egg)))
        if opcode.startswith('fetch_'):
            self._fetch(egg, force=int(opcode[-1]))
        elif opcode == 'remove':
            self._remove_egg(egg)
        elif opcode == 'install':
            name, version = egg_name_to_name_version(egg)
            package = self._remote_repository.find_package(name, version)
            extra_info = package.s3index_data
            self._install_egg(os.path.join(self.local_dir, egg), extra_info)
        else:
            raise Exception("unknown opcode: %r" % opcode)

    @contextlib.contextmanager
    def _enpkg_progress_manager(self, execution_context):
        self.super_id = None

        progress = progress_manager_factory("super", "",
                                            execution_context.n_actions,
                                            self.evt_mgr, self, self.super_id)

        try:
            yield progress
        finally:
            self.super_id = uuid4()

    def get_execute_context(self, actions):
        return _ExecuteContext(self.prefixes[0], actions)

    def execute(self, actions):
        """
        Execute actions, which is an iterable over tuples(action, egg_name),
        where action is one of 'fetch', 'remote', or 'install' and egg_name
        is the filename of the egg.
        This method is only meant to be called with actions created by the
        *_actions methods below.
        """
        logger.info("Enpkg.execute: %d", len(actions))

        context = self.get_execute_context(actions)

        with self._enpkg_progress_manager(context) as progress:
            for n, (opcode, egg) in enumerate(context.iter_actions()):
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
        req = Req.from_anything("enstaller")
        eggs = Resolve(self._remote_repository).install_sequence(req, mode)
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
        eggs = Resolve(self._remote_repository).install_sequence(req, mode)
        unavailables = []
        for egg in eggs:
            name, version = egg_name_to_name_version(egg)
            package = self._remote_repository.find_package(name, version)
            if not package.available:
                unavailables.append(egg)
        if len(unavailables) > 0:
            raise UnavailablePackage(req)
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
            installed_packages = self._top_installed_repository.find_packages(name)
            assert len(installed_packages) < 2
            if len(installed_packages) == 1:
                installed_package = installed_packages[0]
                res.append(('remove', installed_package.key))
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
            name, _ = egg_name_to_name_version(egg)
            for installed in self._top_installed_repository.find_packages(name):
                if installed.key == egg:
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
        if req.version and req.build:
            full_version = "{0}-{1}".format(req.version, req.build)
        else:
            full_version = None
        packages = self._top_installed_repository.find_packages(req.name,
                                                                full_version)
        if len(packages) == 0:
            raise EnpkgError("package %s not installed in: %r" %
                             (req, self.prefixes[0]))
        return [('remove', packages[0].key)]

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
                if self._remote_repository._has_package_key(egg):
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

    def _fetch(self, egg, force=False):
        self._downloader.super_id = getattr(self, 'super_id', None)
        self._downloader.fetch_egg(egg, force, self._execution_aborted)
