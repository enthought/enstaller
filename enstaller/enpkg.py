from __future__ import print_function

import contextlib
import logging
import os
import threading
import sys

from uuid import uuid4
from os.path import isfile, join

from egginst.main import EggInst, remove_egg_cli
from egginst.progress import (console_progress_manager_factory,
                              progress_manager_factory)

from enstaller.errors import EnpkgError
from enstaller.eggcollect import meta_dir_from_prefix
from enstaller.repository import (InstalledPackageMetadata, Repository,
                                  egg_name_to_name_version)

from enstaller.history import History
from enstaller.solver import Solver


logger = logging.getLogger(__name__)


class _ActionReprMixing(object):
    def __str__(self):
        return "{}: <{}>".format(self.__class__.__name__, self._egg)

class FetchAction(_ActionReprMixing):
    def __init__(self, downloader, egg, force=True):
        self._downloader = downloader
        self._egg = egg
        self._force = force

    def execute(self):
        downloader = self._downloader
        downloader.super_id = getattr(self, 'super_id', None)

        downloader.fetch(self._egg, self._force)


class InstallAction(_ActionReprMixing):
    def __init__(self, enpkg, egg):
        self._enpkg = enpkg
        self._egg = egg

        self._egg_path = os.path.join(self._enpkg._downloader.cache_directory,
                                      self._egg)

        def _progress_factory(filename, installed_size):
            return console_progress_manager_factory("installing egg", filename,
                                                    installed_size)

        self._progress_factory = _progress_factory
        self._progress = None

    def progress_update(self, step):
        self._progress(step=step)

    def _extract_extra_info(self):
        name, version = egg_name_to_name_version(self._egg)
        package = self._enpkg._remote_repository.find_package(name, version)
        return package.s3index_data

    def iter_execute(self):
        extra_info = self._extract_extra_info()

        installer = EggInst(self._egg_path, prefix=self._enpkg.top_prefix,
                                  evt_mgr=self._enpkg.evt_mgr)
        if self._enpkg.evt_mgr is not None:
            installer.super_id = getattr(self._enpkg, 'super_id', None)

        self._progress = self._progress_factory(installer.fn,
                                                installer.installed_size)

        with self._progress:
            for step in installer.install_iterator(extra_info):
                yield step

        self._post_install()

    def __iter__(self):
        return self.iter_execute()

    def execute(self):
        for currently_extracted_size in self.iter_execute():
            self.progress_update(currently_extracted_size)

    def _post_install(self):
        name, _ = egg_name_to_name_version(self._egg_path)
        meta_dir = meta_dir_from_prefix(self._enpkg.top_prefix, name)
        package = InstalledPackageMetadata.from_meta_dir(meta_dir)

        self._enpkg._top_installed_repository.add_package(package)
        self._enpkg._installed_repository.add_package(package)


class RemoveAction(_ActionReprMixing):
    def __init__(self, enpkg, egg):
        self._enpkg = enpkg
        self._egg = egg

        def _progress_factory(filename, installed_size):
            return console_progress_manager_factory("removing egg", filename,
                                                    installed_size)

        self._progress_factory = _progress_factory
        self._progress = None

    def progress_update(self, step):
        self._progress(step=step)

    def __iter__(self):
        return self.iter_execute()

    def iter_execute(self):
        installer = EggInst(self._egg, self._enpkg.top_prefix, False,
                            self._enpkg.evt_mgr)
        remover = installer._egginst_remover
        if not remover.is_installed:
            logger.error("Error: can't find meta data for: %r", remover.cname)
            return

        if self._enpkg.evt_mgr is not None:
            remover = EggInst(self._egg, prefix=self._enpkg.top_prefix,
                              evt_mgr=self._enpkg.evt_mgr)
            remover.super_id = getattr(self._enpkg, 'super_id', None)

        self._progress = self._progress_factory(installer.fn, remover.installed_size)

        with self._progress:
            for n, filename in enumerate(remover.remove_iterator()):
                yield n

        # FIXME: we recalculate the full repository because we don't have a
        # feature to remove a package yet
        self._top_installed_repository = \
            Repository._from_prefixes([self._enpkg.top_prefix])

    def execute(self):
        for n in self.iter_execute():
            self.progress_update(n)


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

        self.evt_mgr = evt_mgr

        self._remote_repository = remote_repository

        self._installed_repository = Repository._from_prefixes(self.prefixes)
        self._top_installed_repository = Repository._from_prefixes([self.top_prefix])

        self._execution_aborted = threading.Event()

        self._downloader = download_manager
        # XXX: will be removed once the execution_aborted is not passed across
        # classes anymore
        self._downloader._execution_aborted = self._execution_aborted

        self._solver = Solver(self._remote_repository,
                              self._top_installed_repository)

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

    class _ExecuteContext(object):
        def __init__(self, actions, enpkg):
            self._top_prefix = enpkg.top_prefix
            self._actions = actions
            self._remote_repository = enpkg._remote_repository
            self._enpkg = enpkg

        def _action_factory(self, action):
            opcode, egg = action

            if opcode.startswith('fetch_'):
                force = int(opcode[-1])
                return FetchAction(self._enpkg._downloader, egg, force)
            elif opcode.startswith("install"):
                return InstallAction(self._enpkg, egg)
            elif opcode.startswith("remove"):
                return RemoveAction(self._enpkg, egg)
            else:
                raise ValueError("Unknown opcode: {0!r}".format(opcode))

        def __iter__(self):
            with History(self._top_prefix):
                for action in self._actions:
                    logger.info('\t' + str(action))
                    yield self._action_factory(action)

    def execute_context(self, actions):
        return self._ExecuteContext(actions, self)

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

        with self._enpkg_progress_manager(len(actions)) as progress:
            self._execute(actions, progress)

    def _execute(self, actions, progress):
        for n, action in enumerate(self.execute_context(actions)):
            if self._execution_aborted.is_set():
                self._execution_aborted.clear()
                break
            action.execute()
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
