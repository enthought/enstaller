from enum import Enum

from enstaller.errors import EnpkgError

from .request import JobType
from .requirement import _LegacyRequirement, Requirement
from .resolve import SolverMode, Resolve


class ForceMode(Enum):
    NONE = 0
    MAIN_ONLY = 1
    ALL = 2


class Solver(object):
    def __init__(self, remote_repository, top_installed_repository,
                 mode=SolverMode.RECUR, force=ForceMode.NONE):
        self._remote_repository = remote_repository
        self._top_installed_repository = top_installed_repository

        self.mode = mode
        self.force = force

    def resolve(self, request):
        operations = []

        for job in request.jobs:
            if job.kind == JobType.install:
                assert isinstance(job.requirement, Requirement)
                legacy_requirement = _LegacyRequirement(job.requirement)
                operations.extend(self._install(legacy_requirement))
            elif job.kind == JobType.remove:
                assert isinstance(job.requirement, Requirement)
                legacy_requirement = _LegacyRequirement(job.requirement)
                operations.extend(("remove", p) for p in
                                  self._remove(legacy_requirement))
            else:
                raise ValueError("Unsupported job kind: {0}".format(job.kind))

        return operations

    def _install(self, requirement):
        eggs = Resolve(self._remote_repository).install_sequence(requirement,
                                                                 self.mode)
        return self._install_actions(eggs, self.mode, self.force)

    def _remove(self, requirement):
        packages = self._top_installed_repository.find_packages(
            requirement.name)
        if len(packages) == 0:
            raise EnpkgError("package %s not installed" % (requirement, ))
        return [packages[0].key]

    def _install_actions(self, packages, mode, force):
        if force == ForceMode.NONE:
            # remove already installed packages from package list
            packages = self._filter_installed_packages(packages)
        elif force == ForceMode.MAIN_ONLY:
            packages = self._filter_installed_packages(packages[:-1]) + [packages[-1]]

        # remove packages with the same name (from first package collection
        # only, in reverse install order)
        res = []
        for package in reversed(packages):
            name = package.name
            installed_packages = self._top_installed_repository.find_packages(name)
            assert len(installed_packages) < 2
            if len(installed_packages) == 1:
                installed_package = installed_packages[0]
                res.append(('remove', installed_package))
        for package in packages:
            res.append(('install', package))
        return res

    def _filter_installed_packages(self, packages):
        """ Filter out already installed packages from the given package list.

        Parameters
        ----------
        packages: seq
            List of PackageMetadata instances
        """
        filtered_packages = []
        for package in packages:
            name = package.name
            for installed in self._top_installed_repository.find_packages(name):
                if installed.key == package.key:
                    break
            else:
                filtered_packages.append(package)
        return filtered_packages
