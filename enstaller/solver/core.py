from enstaller.utils import PY_VER

import enstaller

from enstaller.egg_meta import split_eggname
from enstaller.errors import EnpkgError
from enstaller.repository import (egg_name_to_name_version, Repository,
                                  RepositoryPackageMetadata)

from .resolve import Resolve


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


def install_actions_enstaller(remote_repository, installed_repository):
    latest = remote_repository.find_latest_package("enstaller")

    if latest.version == enstaller.__version__:
        return []
    else:
        actions = [("fetch", latest.key)]

        installed_enstallers = installed_repository.find_packages(latest.name)
        if len(installed_enstallers) >= 1:
            actions.append(("remove", latest.key))

        actions.append(("install", latest.key))
        return actions


class Solver(object):
    def __init__(self, remote_repository, top_installed_repository,
                 mode='recur', force=False, forceall=False):
        self._remote_repository = remote_repository
        self._top_installed_repository = top_installed_repository

        self.mode = mode
        self.force = force
        self.forceall = forceall

    def resolve(self, request):
        operations = []

        for job in request.jobs:
            if job.kind == "install":
                operations.extend(self._install(job.requirement))
            elif job.kind == "remove":
                operations.extend(("remove", p) for p in
                                  self._remove(job.requirement))
            else:
                raise ValueError("Unsupported job kind: {0}".format(job.kind))

        return operations

    def _install(self, requirement):
        eggs = Resolve(self._remote_repository).install_sequence(requirement,
                                                                 self.mode)
        return self._install_actions(eggs, self.mode, self.force,
                                     self.forceall)

    def _remove(self, requirement):
        if requirement.version and requirement.build:
            full_version = "{0}-{1}".format(requirement.version,
                                            requirement.build)
        else:
            full_version = None
        packages = self._top_installed_repository.find_packages(
                requirement.name, full_version)
        if len(packages) == 0:
            raise EnpkgError("package %s not installed" % (requirement, ))
        return [packages[0].key]

    def _install_actions(self, eggs, mode, force, forceall):
        if not self.forceall:
            # remove already installed eggs from egg list
            if self.force:
                eggs = self._filter_installed_eggs(eggs[:-1]) + [eggs[-1]]
            else:
                eggs = self._filter_installed_eggs(eggs)

        # remove packages with the same name (from first egg collection
        # only, in reverse install order)
        res = []
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
