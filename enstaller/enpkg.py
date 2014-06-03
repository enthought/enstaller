from __future__ import print_function

import contextlib
import logging
import os
import threading
import sys

from uuid import uuid4
from os.path import isfile, join

from egginst.main import EggInst, install_egg_cli, remove_egg_cli
from egginst.progress import progress_manager_factory

from enstaller.errors import EnpkgError
from enstaller.eggcollect import meta_dir_from_prefix
from enstaller.repository import (InstalledPackageMetadata, Repository,
                                  egg_name_to_name_version)

from enstaller.history import History
from enstaller.solver import Solver


logger = logging.getLogger(__name__)


class EggInstaller(object):
    def __init__(self, prefix, event_manager=None):
        self.prefix = prefix
        self.event_manager = event_manager

    def install(self, path, extra_info=None):
        if self.event_manager is None:
            install_egg_cli(path, self.prefix, extra_info=extra_info)
        else:
            installer = EggInst(path, prefix=self.prefix, evt_mgr=self.evt_mgr)
            installer.super_id = getattr(self, 'super_id', None)
            installer.install(extra_info)

    def remove(self, name):
        if self.event_manager is None:
            remove_egg_cli(name, self.prefix)
        else:
            remover = EggInst(name, prefix=self.prefix, evt_mgr=self.evt_mgr)
            remover.super_id = getattr(self, 'super_id', None)
            remover.remove()


class Enpkg(object):
    """ This is main interface for using enpkg, it is used by the CLI.
    Arguments for object creation:

    Parameters
    ----------
    repository: Repository
        This is the remote repository which enpkg will use to resolve
        dependencies.
    download_manager: DownloadManager
        The download manager used to fetch eggs.
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
                 prefixes=[sys.prefix], evt_mgr=None):
        self.prefixes = prefixes
        self.top_prefix = prefixes[0]

        self._installer = EggInstaller(self.top_prefix, event_manager=evt_mgr)
        self.evt_mgr = evt_mgr

        self._remote_repository = remote_repository

        self._installed_repository = Repository._from_prefixes(self.prefixes)
        self._top_installed_repository = Repository._from_prefixes([self.top_prefix])

        self._execution_aborted = threading.Event()

        self._downloader = download_manager

        self._solver = Solver(self._remote_repository,
                              self._top_installed_repository)

    def _install_egg(self, path, extra_info=None):
        """
        Install the given egg.

        Parameters
        ----------
        path: str
            The path to the egg to install
        """
        name, _ = egg_name_to_name_version(path)

        self._installer.install(path, extra_info)

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
        self._installer.remove(egg)

        # FIXME: we recalculate the full repository because we don't have a
        # feature to remove a package yet
        self._top_installed_repository = \
            Repository._from_prefixes([self.prefixes[0]])

    def _execute_fetch(self, opcode, egg):
        self._fetch(egg, force=int(opcode[-1]))

    def _execute_remove(self, opcode, egg):
        self._remove_egg(egg)

    def _execute_install(self, opcode, egg):
        name, version = egg_name_to_name_version(egg)
        package = self._remote_repository.find_package(name, version)
        extra_info = package.s3index_data
        self._install_egg(os.path.join(self._downloader.cache_directory, egg),
                          extra_info)

    def _execute_opcode(self, opcode, egg):
        logger.info('\t' + str((opcode, egg)))
        if opcode.startswith('fetch_'):
            self._execute_fetch(opcode, egg)
        elif opcode == 'remove':
            self._execute_remove(opcode, egg)
        elif opcode == 'install':
            self._execute_install(opcode, egg)
        else:
            raise Exception("unknown opcode: %r" % opcode)

    @contextlib.contextmanager
    def _enpkg_progress_manager(self, n_actions):
        self.super_id = None

        progress = progress_manager_factory("super", "",
                                            n_actions,
                                            self.evt_mgr, self, self.super_id)

        try:
            yield progress
        finally:
            self.super_id = uuid4()

    def execute(self, actions):
        """
        Execute the given set of actions.

        This method is only meant to be called with actions created by the
        *_actions methods below.

        Parameters
        ----------
        actions : list
            List of (opcode, egg) pairs, as returned by the *_actions from
            Solver.
        """
        logger.info("Enpkg.execute: %d", len(actions))

        with History(self.top_prefix):
            with self._enpkg_progress_manager(len(actions)) as progress:
                self._execute(actions, progress)

    def _execute(self, actions, progress):
        for n, (opcode, egg) in enumerate(actions):
            if self._execution_aborted.is_set():
                self._execution_aborted.clear()
                break
            self._execute_opcode(opcode, egg)
            progress(step=n)

    def abort_execution(self):
        self._execution_aborted.set()

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
            if not isfile(join(self._downloader.cache_directory, egg)):
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
