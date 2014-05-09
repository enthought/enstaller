from enstaller.utils import PY_VER

import enstaller

from enstaller.egg_meta import split_eggname
from enstaller.errors import EnpkgError, UnavailablePackage
from enstaller.repository import (egg_name_to_name_version, Repository,
                                  RepositoryPackageMetadata)
from enstaller.resolve import Req, Resolve


def create_enstaller_update_repository(repository, version):
    """
    Create a new repository with an additional fake package 'enstaller' at the
    currently running version.

    Parameters
    ----------
    repository: Repository
        Current repository
    version: str
        Version of enstaller to inject

    Returns
    -------
    """
    name = "enstaller"
    build = 1
    key = "{0}-{1}-{2}.egg".format(name, version, build)
    current_enstaller = RepositoryPackageMetadata(key, name, version, build,
                                                  [], PY_VER, -1, "a" * 32,
                                                  0.0, "free", True,
                                                  "mocked_store")

    new_repository = Repository()
    for package in repository.iter_packages():
        new_repository.add_package(package)
    new_repository.add_package(current_enstaller)

    return new_repository


class Solver(object):
    def __init__(self, remote_repository, top_installed_repository):
        self._remote_repository = remote_repository
        self._top_installed_repository = top_installed_repository

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

        Parameters
        ----------
        eggs: seq
            List of egg filenames
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
            raise EnpkgError("package %s not installed" % (req, ))
        return [('remove', packages[0].key)]
