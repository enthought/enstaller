import logging
import operator
from collections import defaultdict

from enum import Enum

from enstaller.errors import MissingDependency, NoPackageFound

from .requirement import Requirement

logger = logging.getLogger(__name__)


class SolverMode(Enum):
    ROOT = 0
    FLAT = 1
    RECUR = 2


class Resolve(object):
    """
    The main purpose of this class is to support the install_sequence method
    below.  In most cases, the user will only create an instance of this
    class (which is inexpensive), to call the install_sequence method, e.g.:

    eggs = Resolve(repository).install_sequence(req)
    """
    def __init__(self, repository):
        """
        Create a new Resolve instance

        Parameters
        ----------
        repository: repository
            The repository instance to use to query package metadata
        """
        self.repository = repository

    def _latest_package(self, requirement):
        """
        return the package with the largest version and build number
        """
        assert requirement.strictness >= 1
        d = dict((package.key, package) for package in
                 self.repository.find_packages(requirement.name))
        matches = [
            package for package in d.values() if requirement.matches(package)
        ]
        if len(matches) == 0:
            return None
        else:
            return max(matches, key=operator.attrgetter("version"))

    def are_complete(self, packages):
        """
        return True if the 'packages' are complete, i.e. the for each egg all
        dependencies (by name only) are also included in 'packages'
        """
        names = set(p.name for p in packages)
        for package in packages:
            for r in self._dependencies_from_package(package):
                if r.name not in names:
                    return False
        return True

    def _determine_install_order(self, packages):
        """
        given the 'packages' (which are already complete, i.e. the for each
        package all dependencies are also included in 'packages'), return a list
        of the same packages in the correct install order
        """
        packages = list(packages)
        assert self.are_complete(packages)

        # make sure each project name is listed only once
        assert len(packages) == len(set(p.name for p in packages))

        # the packages corresponding to the requirements must be sorted
        # because the output of this function is otherwise not deterministic
        packages.sort(key=operator.attrgetter("name"))

        # maps package -> set of required (project) names
        rns = {}
        for package in packages:
            rns[package] = set(r.name for r in self._dependencies_from_package(package))

        # as long as we have things missing, simply look for things which
        # can be added, i.e. all the requirements have been added already
        result = []
        names_inst = set()
        while len(result) < len(packages):
            n = len(result)
            for package in packages:
                if package in result:
                    continue
                # see if all required packages were added already
                if all(bool(name in names_inst) for name in rns[package]):
                    result.append(package)
                    names_inst.add(package.name)
                    assert len(names_inst) == len(result)

            if len(result) == n:
                # nothing was added
                raise Exception("Loop in dependency graph\n%r" % packages)
        return result

    def _sequence_flat(self, root):
        eggs = [root]
        for r in self._dependencies_from_egg(root):
            d = self._latest_egg(r)
            if d is None:
                from enstaller.enpkg import EnpkgError
                err = EnpkgError('Error: could not resolve %s' % str(r))
                err.req = r
                raise err
            eggs.append(d)

        can_order = self.are_complete(eggs)
        logger.info("Can determine install order: %r", can_order)
        if can_order:
            eggs = self._determine_install_order(eggs)
        return eggs

    def _dependencies_from_package(self, package):
        """
        return the set of requirement objects listed by the given package
        """
        return set(Requirement(s) for s in package.dependencies)

    def _sequence_recur(self, root):
        reqs_shallow = {}
        for r in self._dependencies_from_package(root):
            reqs_shallow[r.name] = r
        reqs_deep = defaultdict(set)

        def add_dependents(package, visited=None):
            if visited is None:
                visited = set()
            visited.add(package)
            for r in self._dependencies_from_package(package):
                reqs_deep[r.name].add(r)
                if (r.name in reqs_shallow and
                        r.strictness < reqs_shallow[r.name].strictness):
                    continue
                d = self._latest_package(r)
                if d is None:
                    msg = "Could not resolve \"%s\" " \
                          "required by \"%s\"" % (str(r), package)
                    raise MissingDependency(msg, package, r)
                packages.add(d)
                if d not in visited:
                    add_dependents(d, visited)

        packages = set([root])
        add_dependents(root)

        names = set(p.name for p in packages)
        if len(packages) != len(names):
            for name in names:
                ds = [d for d in packages if self._name_from_package(d) == name]
                assert len(ds) != 0
                if len(ds) == 1:
                    continue
                logger.info('multiple: %s', name)
                for d in ds:
                    logger.info('    %s', d)
                r = max(reqs_deep[name], key=lambda r: r.strictness)
                assert r.name == name
                # remove the packages with name
                packages = [d for d in packages if self._name_from_package(d) != name]
                # add the one
                packages.append(self._latest_package(r))

        return self._determine_install_order(packages)

    def install_sequence(self, req, mode=SolverMode.RECUR):
        """
        Return the list of eggs which need to be installed (and None if
        the requirement can not be resolved).
        The returned list is given in dependency order.
        The 'mode' may be:

        'SolverMode.ROOT':  only the egg for the requirement itself is
                            contained in the result (but not any
                            dependencies)

        'SolverMode.FLAT':  dependencies are handled only one level deep

        'SolverMode.RECUR': dependencies are handled recursively (default)
        """
        logger.info("Determining install sequence for %r", req)
        root = self._latest_package(req)
        if root is None:
            msg = "No egg found for requirement {0!r}.".format(str(req))
            raise NoPackageFound(msg, req)
        if mode == SolverMode.ROOT:
            return [root]
        elif mode == SolverMode.FLAT:
            return self._sequence_flat(root)
        elif mode == SolverMode.RECUR:
            return self._sequence_recur(root)
        else:
            raise Exception('did not expect: mode = %r' % mode)
