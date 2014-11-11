import re

from enstaller.egg_meta import is_valid_eggname, split_eggname


class Requirement(object):
    """
    A requirement object is initialized by a requirement string. Attributes:
    name: the lowercase project name
    version: the list of possible versions required
    strictness: the level of strictness
        0   nothing matters, anything matches
        1   only the name must match
        2   name and version must match
        3   name, version and build must match
    """
    @classmethod
    def from_anything(cls, arg):
        if isinstance(arg, cls):
            return arg
        elif is_valid_eggname(arg):
            return cls('%s %s-%d' % split_eggname(arg))
        else:
            return cls(arg)

    pat = re.compile(r'(?:([\w.]+)(?:\s+([\w.]+)(?:-(\d+))?)?)?$')

    def __init__(self, req_string):
        m = self.pat.match(str(req_string.strip()))
        if m is None:
            raise Exception("Not a valid requirement: %r" % req_string)
        self.name, self.version, self.build = m.groups()
        self.strictness = 0
        if self.name is not None:
            self.name = self.name.lower()
            self.strictness = 1
        if self.version is not None:
            self.strictness = 2
        if self.build is not None:
            self.build = int(self.build)
            self.strictness = 3

    def as_dict(self):
        res = {}
        for var_name in 'name', 'version', 'build':
            if getattr(self, var_name):
                res[var_name] = getattr(self, var_name)
        return res

    def matches(self, candidate):
        """
        Returns whether the given package candidate matches the requirement.

        Parameters
        ----------
        candidate: PackageVersionInfo
            The package to test.
        """
        if self.strictness == 0:
            return True
        if candidate.name != self.name:
            return False
        if self.strictness == 1:
            return True
        if str(candidate.version.upstream) != self.version:
            return False
        if self.strictness == 2:
            return True
        return candidate.version.build == self.build

    def __str__(self):
        if self.strictness == 0:
            return ''
        res = self.name
        if self.version:
            res += ' %s' % self.version
        if self.build:
            res += '-%d' % self.build
        return res

    def __repr__(self):
        """
        return a canonical representation of the object
        """
        return 'Requirement(%r)' % str(self)

    def __eq__(self, other):
        return (self.name == other.name and
                self.version == other.version and
                self.build == other.build and
                self.strictness == other.strictness)

    def __hash__(self):
        return (hash(self.strictness) ^ hash(self.name) ^
                hash(self.version) ^ hash(self.build))
