from __future__ import print_function

import logging
import os
import sys

from os.path import isfile, join

from egginst.main import EggInst, _default_runtime_info
from egginst.progress import dummy_progress_bar_factory

from enstaller.errors import EnpkgError, InvalidChecksum, NoSuchPackage
from enstaller.eggcollect import meta_dir_from_prefix
from enstaller.fetch import _DownloadManager
from enstaller.package import egg_name_to_name_version
from enstaller.repository import (InstalledPackageMetadata, Repository)

from enstaller.history import History
from enstaller.solver import ForceMode, Solver, SolverMode


_DEFAULT_MAX_RETRIES = 2

logger = logging.getLogger(__name__)


class _BaseAction(object):
    def __init__(self):
        self._is_canceled = False

    def __str__(self):
        return "{}: <{}>".format(self.__class__.__name__, self._egg)

    @property
    def is_canceled(self):
        return self._is_canceled

    def cancel(self):
        """ Cancel the action.

        Note: may not do anything for operations that cannot be safely
        canceled.
        """
        self._is_canceled = True

    def execute(self):
        """ Execute the given action."""

    def iter_execute(self):
        """ Iterator wich execute the action step by step when iterated
        over."""

    def __iter__(self):
        return self.iter_execute()


class FetchAction(_BaseAction):
    def __init__(self, package, downloader, remote_repository, force=True,
                 progress_bar_factory=dummy_progress_bar_factory,
                 max_retries=_DEFAULT_MAX_RETRIES):
        super(FetchAction, self).__init__()
        self._downloader = downloader
        self._package = package
        self._force = force
        self._remote_repository = remote_repository

        self._progress_bar_factory = progress_bar_factory
        self._progress = None

        self._current_context = None
        self._retries = max_retries + 1

    def cancel(self):
        super(FetchAction, self).cancel()
        self._current_context.cancel()

    def progress_update(self, step):
        self._progress.update(step)

    def iter_execute(self):
        context = self._downloader.iter_fetch(self._package, self._force)
        if not context.needs_to_download:
            return

        self._current_context = context

        progress = self._progress_bar_factory(self._package.key,
                                              self._package.size)

        with progress as progress:
            self._progress = progress
            for chunk_size in context.iter_content():
                yield len(chunk_size)

    def execute(self):
        for i in range(self._retries):
            try:
                for chunk_size in self.iter_execute():
                    self.progress_update(chunk_size)
            except InvalidChecksum:
                if i >= self._retries - 1:
                    raise
            else:
                return


class InstallAction(_BaseAction):
    def __init__(self, package, runtime_info, remote_repository,
                 top_installed_repository, installed_repository,
                 cache_directory,
                 progress_bar_factory=dummy_progress_bar_factory):
        super(InstallAction, self).__init__()

        self._runtime_info = runtime_info
        self._package = package
        self._package_path = os.path.join(cache_directory, self._package.key)
        self._remote_repository = remote_repository
        self._top_installed_repository = top_installed_repository
        self._installed_repository = installed_repository

        self._progress_factory = progress_bar_factory
        self._progress = None

    def progress_update(self, step):
        self._progress.update(step)

    def _extract_extra_info(self):
        return self._package.s3index_data

    def iter_execute(self):
        extra_info = self._extract_extra_info()

        installer = EggInst(self._package_path, runtime_info=self._runtime_info)

        progress = self._progress_factory(installer.fn,
                                          installer.installed_size)

        with progress as progress:
            self._progress = progress
            for step in installer.install_iterator(extra_info):
                yield step

        self._post_install()

    def execute(self):
        for currently_extracted_size in self.iter_execute():
            self.progress_update(currently_extracted_size)

    def _post_install(self):
        name, _ = egg_name_to_name_version(self._package_path)
        meta_dir = meta_dir_from_prefix(self._runtime_info.prefix, name)
        package = InstalledPackageMetadata.from_meta_dir(meta_dir)

        self._top_installed_repository.add_package(package)
        self._installed_repository.add_package(package)


class RemoveAction(_BaseAction):
    def __init__(self, package, runtime_info, top_installed_repository,
                 installed_repository,
                 progress_bar_factory=dummy_progress_bar_factory):
        super(RemoveAction, self).__init__()
        self._package = package
        self._runtime_info = runtime_info

        self._top_installed_repository = top_installed_repository
        self._installed_repository = installed_repository

        self._progress_factory = progress_bar_factory
        self._progress = None

    def progress_update(self, step):
        self._progress.update(step)

    def iter_execute(self):
        installer = EggInst(self._package.key, runtime_info=self._runtime_info)
        remover = installer._egginst_remover
        if not remover.is_installed:
            logger.error("Error: can't find meta data for: %r", remover.cname)
            return
        progress = self._progress_factory(installer.fn,
                                          remover.installed_size,
                                          len(remover.files))

        with progress as progress:
            self._progress = progress
            for filename in remover.remove_iterator():
                yield 1

        self._top_installed_repository.delete_package(self._package)
        self._installed_repository.delete_package(self._package)

    def execute(self):
        for n in self.iter_execute():
            self.progress_update(n)


class ProgressBarContext(object):
    def __init__(self, default_progress_bar_factory, **kw):
        """
        A simple object holding progress bar factories to be used by actions.

        Parameters
        ----------
        default_progress_bar_factory : callable
            The default progress bar factory
        **kw :
            action_name -> callable pairs. For each specified action, this
            specific callable will be used instead of the default factory.

        .. note:: each callable signature must be (label, filename, size)
        """
        self.default_progress_bar_factory = default_progress_bar_factory

        self.fetch_progress_factory = kw.get("fetch",
                                             default_progress_bar_factory)
        self.install_progress_factory = kw.get("install",
                                               default_progress_bar_factory)
        self.remove_progress_factory = kw.get("remove",
                                              default_progress_bar_factory)

    def fetch_progress(self, filename, size):
        return self.fetch_progress_factory("fetching", filename, size)

    def install_progress(self, filename, size):
        return self.install_progress_factory("installing egg", filename, size)

    def remove_progress(self, filename, size, steps):
        return self.remove_progress_factory("removing egg", filename, size,
                                            steps)


class _ExecuteContext(object):
    def __init__(self, actions, enpkg, progress_bar_context, force=False,
                 max_retries=_DEFAULT_MAX_RETRIES):
        self._top_prefix = enpkg.top_prefix
        self._actions = actions
        self._remote_repository = enpkg._remote_repository
        self._enpkg = enpkg
        self._force = force

        self._pbar_context = progress_bar_context

        self._max_retries = max_retries

    def _action_factory(self, action):
        opcode, egg = action

        if opcode.startswith('fetch'):
            return FetchAction(egg, self._enpkg._downloader,
                               self._remote_repository, self._force,
                               self._pbar_context.fetch_progress,
                               self._max_retries)
        elif opcode.startswith("install"):
            return InstallAction(egg, self._enpkg._runtime_info,
                                 self._enpkg._remote_repository,
                                 self._enpkg._top_installed_repository,
                                 self._enpkg._installed_repository,
                                 self._enpkg._downloader.cache_directory,
                                 self._pbar_context.install_progress)
        elif opcode.startswith("remove"):
            return RemoveAction(egg, self._enpkg._runtime_info,
                                self._enpkg._top_installed_repository,
                                self._enpkg._installed_repository,
                                self._pbar_context.remove_progress)
        else:
            raise ValueError("Unknown opcode: {0!r}".format(opcode))

    def __iter__(self):
        with History(self._top_prefix):
            for action in self._actions:
                logger.info('\t' + str(action))
                yield self._action_factory(action)


class Enpkg(object):
    """ This is main interface for using enpkg, it is used by the CLI.
    Arguments for object creation:

    Parameters
    ----------
    repository : Repository
        This is the remote repository which enpkg will use to resolve
        dependencies.
    session : Session
        The session used to connect to the remote server (fetching indices,
        eggs, etc...).
    prefixes : list of paths -- default: [sys.prefix]
        Each path, is an install "prefix" (such as, e.g. /usr/local) in which
        things get installed. Eggs are installed or removed from the first
        prefix in the list.
    progress_context : ProgressBarContext
        If specified, will be used for progress bar management across all
        executed actions. If None, use dummy (do nothing) progress bars.
    max_retries : int
        Maximum number of retries to fetch an egg when checksum mismatchs
        occur.
    """
    def __init__(self, remote_repository, session,
                 prefixes=[sys.prefix], progress_context=None,
                 force=False, max_retries=_DEFAULT_MAX_RETRIES,
                 runtime_info=None):
        self.prefixes = prefixes
        self.top_prefix = prefixes[0]

        self._runtime_info = (
            runtime_info or _default_runtime_info(self.top_prefix)
        )

        self._remote_repository = remote_repository

        self._installed_repository = Repository._from_prefixes(self.prefixes)
        self._top_installed_repository = \
            Repository._from_prefixes([self.top_prefix])

        self._session = session
        self._downloader = _DownloadManager(session, remote_repository)

        self._progress_context = progress_context or \
            ProgressBarContext(dummy_progress_bar_factory)

        self._force = force
        self.max_retries = max_retries

    def _solver_factory(self, mode=SolverMode.RECUR, force=ForceMode.NONE):
        solver = Solver(self._remote_repository,
                        self._top_installed_repository,
                        mode, force)
        return solver

    def execute_context(self, actions):
        return _ExecuteContext(actions, self, self._progress_context,
                               self._force)

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
        for action in self.execute_context(actions):
            action.execute()

    def revert_actions(self, arg):
        """
        Calculate the actions necessary to revert to a given state, the
        argument may be one of:
          * complete set of eggs, i.e. a set of egg file names
          * revision number (negative numbers allowed)
        """
        h = History(self.top_prefix)
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
                eggname, version = egg_name_to_name_version(egg)
                try:
                    self._remote_repository.find_package(eggname, version)
                    res.append(('fetch_0', egg))
                except NoSuchPackage:
                    raise EnpkgError("cannot revert -- missing %r" % egg)
            res.append(('install', egg))
        return res

    def get_history(self):
        """
        return a history (h) object with this Enpkg instance prefix.
        """
        # FIXME: only used by canopy
        return History(self.top_prefix)
