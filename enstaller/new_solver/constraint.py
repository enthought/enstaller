from enstaller.versions.enpkg import EnpkgVersion

from .constraints_parser import _RawConstraintsParser
from .constraint_types import (Any, EnpkgUpstreamMatch, Equal, GEQ, GT,
                               LEQ, LT, Not)


def are_compatible(left_constraint, candidate_version):
    return left_constraint.matches(candidate_version)


class MultiConstraints(object):
    """
    A set of constraints to match a version against.

    Example
    -------

    >>> V = EnpkgVersion.from_string
    >>> m = MultiConstraints(GEQ(V("1.3.0-1")))
    >>> m.matches(V("1.3.0-1"))
    True
    >>> m.matches(V("1.2.0-1"))
    False
    """
    @classmethod
    def _from_string(cls, requirement_string,
                     version_factory=EnpkgVersion.from_string):
        """Creates a MultiConstraints from a requirement string.

        Mostly useful to write readable tests, do not use in actual
        code.
        """
        parser = _RawConstraintsParser()
        return cls(parser.parse(requirement_string, version_factory))

    def __init__(self, constraints=None):
        self._constraints = set() or constraints

    def matches(self, version_candidate):
        """ Returns True if the given version matches this set of
        requirements.

        Parameters
        ----------
        version_candidate : Version
            A comparable version instance. Must match the version class
            used for the set of requirements.
        """
        for constraint in self._constraints:
            if not constraint.matches(version_candidate):
                return False
        return True

    def add_constraint(self, constraint):
        """ Add a constraint to the existing set.

        Parameters
        ----------
        constraint : _Constraint
            A valid constraint instance.
        """
        self._constraints.add(constraint)
