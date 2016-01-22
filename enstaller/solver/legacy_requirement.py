import six

from okonomiyaki.versions import EnpkgVersion
from simplesat.constraints.kinds import Any, Equal, EnpkgUpstreamMatch

from . import Requirement


class _LegacyRequirement(object):
    @classmethod
    def from_requirement_string(cls, requirement_string):
        """ Creates a requirement from a legacy requirement string (as
        found in our current egg metadata, format < 2).

        Parameters
        ----------
        requirement_string : str
            The legacy requirement string, e.g. 'MKL 10.3'
        """
        ret = Requirement.from_legacy_requirement_string(
            requirement_string, EnpkgVersion.from_string
        )
        return cls(ret)

    def __init__(self, requirement):
        constraints = requirement._constraints._constraints
        if len(constraints) == 0:
            self._strictness = 1
        elif len(constraints) == 1:
            constraint = six.next(iter(constraints))
            if isinstance(constraint, Any):
                self._strictness = 1
            elif isinstance(constraint, EnpkgUpstreamMatch):
                self._strictness = 2
            elif isinstance(constraint, Equal):
                self._strictness = 3
            else:
                raise RuntimeError(
                    "Constraint '{0}' cannot be used in requirement used for "
                    "legacy solver".format(constraint)
                )
        else:
            raise RuntimeError(
                "Complex requirement cannot be used in legacy solver"
            )

        self._requirement = requirement

    def matches(self, arg):
        return self._requirement.matches(arg)

    @property
    def name(self):
        return self._requirement.name.lower()

    @property
    def as_dict(self):
        d = {"name": self.name}
        if self._strictness >= 2:
            constraint = six.next(iter(
                self._requirement._constraints._constraints
            ))
            d["version"] = str(constraint.version.upstream)
            if self._strictness == 3:
                d["build"] = str(constraint.version.build)

        return d

    @property
    def strictness(self):
        return self._strictness

    def __str__(self):
        if self.strictness == 0:
            return ''
        res = self.name
        if self.strictness >= 2:
            constraint = six.next(iter(
                self._requirement._constraints._constraints
            ))
            res += ' %s' % str(constraint.version.upstream)
            if self.strictness == 3:
                res += '-%d' % constraint.version.build
        return res

    def __eq__(self, other):
        return self._requirement == other._requirement

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self._requirement)
