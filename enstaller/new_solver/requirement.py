from enstaller.errors import SolverException
from enstaller.versions.enpkg import EnpkgVersion

from .constraints_parser import _RawRequirementParser
from .constraint import MultiConstraints


def _first(iterable):
    for item in iterable:
        return item


class Requirement(object):
    """Requirements instances represent a 'package requirement', that is a
    package + version constraints.

    Arguments
    ---------
    name: str
        PackageInfo name
    specs: seq
        Sequence of constraints
    """
    @classmethod
    def _from_string(cls, string,
                     version_factory=EnpkgVersion.from_string):
        parser = _RawRequirementParser()
        named_constraints = parser.parse(string, version_factory)
        if len(named_constraints) > 1:
            names = named_constraints.keys()
            msg = "Multiple package name for constraint: {0!r}".format(names)
            raise SolverException(names)
        assert len(named_constraints) > 0
        name = _first(named_constraints.keys())
        return cls(name, named_constraints[name])

    def __init__(self, name, constraints=None):
        self.name = name

        self._constraints = MultiConstraints(constraints)

    def matches(self, version_candidate):
        return self._constraints.matches(version_candidate)

    def __eq__(self, other):
        return self.name == other.name \
                and self._constraints == other._constraints

    def __hash__(self):
        return hash((self.name, self._constraints))
