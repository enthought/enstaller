import re

from enstaller.errors import EnstallerException, SolverException
from enstaller.versions.enpkg import EnpkgVersion

from .constraint import MultiConstraints
from .constraint_types import Any, EnpkgUpstreamMatch, Equal
from .constraints_parser import _RawRequirementParser


_FULL_PACKAGE_RE = re.compile("""\
                              (?P<name>[^-.]+)
                              -
                              (?P<version>(.*))
                              $""", re.VERBOSE)


def parse_package_full_name(full_name):
    """
    Parse a package full name (e.g. 'numpy-1.6.0-1') into a (name,
    version_string) pair.
    """
    m = _FULL_PACKAGE_RE.match(full_name)
    if m:
        return m.group("name"), m.group("version")
    else:
        msg = "Invalid package full name {0!r}".format(full_name)
        raise EnstallerException(msg)


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
        """ Creates a requirement from a requirement string.

        Parameters
        ----------
        requirement_string : str
            The requirement string, e.g. 'MKL >= 10.3, MKL < 11.0'
        """
        parser = _RawRequirementParser()
        named_constraints = parser.parse(string, version_factory)
        if len(named_constraints) > 1:
            names = named_constraints.keys()
            msg = "Multiple package name for constraint: {0!r}".format(names)
            raise SolverException(msg)
        assert len(named_constraints) > 0
        name = _first(named_constraints.keys())
        return cls(name, named_constraints[name])

    @classmethod
    def from_legay_requirement_string(cls, requirement_string,
                                      version_factory=EnpkgVersion.from_string):
        """ Creates a requirement from a legacy requirement string (as
        found in our current egg metadata, format < 2).

        Parameters
        ----------
        requirement_string : str
            The legacy requirement string, e.g. 'MKL 10.3'
        """
        parts = requirement_string.split(None, 1)
        if len(parts) == 2:
            name, version_string = parts
            version = version_factory(version_string)
            if version.build == 0:
                return cls(name.lower(), [EnpkgUpstreamMatch(version)])
            else:
                return cls(name.lower(), [Equal(version)])
        elif len(parts) == 1:
            name = parts[0]
            return cls(name.lower(), [Any()])
        else:
            raise ValueError(parts)

    @classmethod
    def from_package_string(cls, package_string,
                            version_factory=EnpkgVersion.from_string):
        """ Creates a requirement from a package full version.

        Parameters
        ----------
        package_string : str
            The package string, e.g. 'numpy-1.8.1-1'
        """
        name, version_string = parse_package_full_name(package_string)
        version = version_factory(version_string)
        return cls(name, [Equal(version)])

    def __init__(self, name, constraints=None):
        self.name = name

        self._constraints = MultiConstraints(constraints)

    def matches(self, version_candidate):
        """ Returns True if the given version matches this set of
        requirements, False otherwise.

        Parameters
        ----------
        version_candidate : obj
            A valid version object (must match the version factory of the
            requirement instance).
        """
        return self._constraints.matches(version_candidate)

    def __eq__(self, other):
        return (self.name == other.name
                and self._constraints == other._constraints)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self.name, self._constraints))
