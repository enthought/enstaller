import logging
from collections import defaultdict

from enstaller.errors import MissingDependency, NoPackageFound
from enstaller.repository import egg_name_to_name_version

from .requirement import Requirement

logger = logging.getLogger(__name__)


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

    def _latest_egg(self, requirement):
        """
        return the egg with the largest version and build number
        """
        assert requirement.strictness >= 1
        d = dict((package.key, package) for package in
                 self.repository.find_packages(requirement.name))
        matches = [key for key, package in d.items()
                   if requirement.matches(package)]
        if len(matches) == 0:
            return None
        else:
            return max(matches, key=lambda k: d[k].version)

    def _dependencies_from_egg(self, egg):
        """
        return the set of requirement objects listed by the given egg
        """
        name, version = egg_name_to_name_version(egg)
        package = self.repository.find_package(name, version)
        return set(Requirement(s) for s in package.dependencies)

    def _name_from_egg(self, egg):
        """
        return the project name for a given egg (from it's meta data)
        """
        name, version = egg_name_to_name_version(egg)
        return self.repository.find_package(name, version).name

    def are_complete(self, eggs):
        """
        return True if the 'eggs' are complete, i.e. the for each egg all
        dependencies (by name only) are also included in 'eggs'
        """
        names = set(self._name_from_egg(d) for d in eggs)
        for egg in eggs:
            for r in self._dependencies_from_egg(egg):
                if r.name not in names:
                    return False
        return True

    def _determine_install_order(self, eggs):
        """
        given the 'eggs' (which are already complete, i.e. the for each
        egg all dependencies are also included in 'eggs'), return a list
        of the same eggs in the correct install order
        """
        eggs = list(eggs)
        assert self.are_complete(eggs)

        # make sure each project name is listed only once
        assert len(eggs) == len(set(self._name_from_egg(d) for d in eggs))

        # the eggs corresponding to the requirements must be sorted
        # because the output of this function is otherwise not deterministic
        eggs.sort(key=self._name_from_egg)

        # maps egg -> set of required (project) names
        rns = {}
        for egg in eggs:
            rns[egg] = set(r.name for r in self._dependencies_from_egg(egg))

        # as long as we have things missing, simply look for things which
        # can be added, i.e. all the requirements have been added already
        result = []
        names_inst = set()
        while len(result) < len(eggs):
            n = len(result)
            for egg in eggs:
                if egg in result:
                    continue
                # see if all required packages were added already
                if all(bool(name in names_inst) for name in rns[egg]):
                    result.append(egg)
                    names_inst.add(self._name_from_egg(egg))
                    assert len(names_inst) == len(result)

            if len(result) == n:
                # nothing was added
                raise Exception("Loop in dependency graph\n%r" % eggs)
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

    def _sequence_recur(self, root):
        reqs_shallow = {}
        for r in self._dependencies_from_egg(root):
            reqs_shallow[r.name] = r
        reqs_deep = defaultdict(set)

        def add_dependents(egg, visited=None):
            if visited is None:
                visited = set()
            visited.add(egg)
            for r in self._dependencies_from_egg(egg):
                reqs_deep[r.name].add(r)
                if (r.name in reqs_shallow and
                        r.strictness < reqs_shallow[r.name].strictness):
                    continue
                d = self._latest_egg(r)
                if d is None:
                    msg = "Could not resolve \"%s\" " \
                          "required by \"%s\"" % (str(r), egg)
                    raise MissingDependency(msg, egg, r)
                eggs.add(d)
                if d not in visited:
                    add_dependents(d, visited)

        eggs = set([root])
        add_dependents(root)

        names = set(self._name_from_egg(d) for d in eggs)
        if len(eggs) != len(names):
            for name in names:
                ds = [d for d in eggs if self._name_from_egg(d) == name]
                assert len(ds) != 0
                if len(ds) == 1:
                    continue
                logger.info('multiple: %s', name)
                for d in ds:
                    logger.info('    %s', d)
                r = max(reqs_deep[name], key=lambda r: r.strictness)
                assert r.name == name
                # remove the eggs with name
                eggs = [d for d in eggs if self._name_from_egg(d) != name]
                # add the one
                eggs.append(self._latest_egg(r))

        return self._determine_install_order(eggs)

    def install_sequence(self, req, mode='recur'):
        """
        Return the list of eggs which need to be installed (and None if
        the requirement can not be resolved).
        The returned list is given in dependency order.
        The 'mode' may be:

        'root':  only the egg for the requirement itself is
                 contained in the result (but not any dependencies)

        'flat':  dependencies are handled only one level deep

        'recur': dependencies are handled recursively (default)
        """
        logger.info("Determining install sequence for %r", req)
        root = self._latest_egg(req)
        if root is None:
            msg = "No egg found for requirement {0!r}.".format(str(req))
            raise NoPackageFound(msg, req)
        if mode == 'root':
            return [root]
        if mode == 'flat':
            return self._sequence_flat(root)
        if mode == 'recur':
            return self._sequence_recur(root)
        raise Exception('did not expect: mode = %r' % mode)
