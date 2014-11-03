from enstaller.versions.enpkg import EnpkgVersion


class _ConstraintType(object):
    pass


class Any(_ConstraintType):
    def matches(self, candidate_version):
        return True


class _VersionConstraint(_ConstraintType):
    def __init__(self, version):
        self.version = version

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.version)

    def _ensure_can_compare(self, candidate_version):
        if candidate_version.__class__ != self.version.__class__:
            msg = "Cannot compare {0!r} and {1!r}"
            raise TypeError(msg.format(candidate_version.__class__,
                                       self.version.__class__))


class Equal(_VersionConstraint):
    def matches(self, candidate_version):
        self._ensure_can_compare(candidate_version)
        return self.version == candidate_version


class Not(_VersionConstraint):
    def matches(self, candidate_version):
        self._ensure_can_compare(candidate_version)
        return self.version != candidate_version


class GEQ(_VersionConstraint):
    def matches(self, candidate_version):
        self._ensure_can_compare(candidate_version)
        return candidate_version >= self.version


class GT(_VersionConstraint):
    def matches(self, candidate_version):
        self._ensure_can_compare(candidate_version)
        return candidate_version > self.version


class LEQ(_VersionConstraint):
    def matches(self, candidate_version):
        self._ensure_can_compare(candidate_version)
        return candidate_version <= self.version


class LT(_VersionConstraint):
    def matches(self, candidate_version):
        self._ensure_can_compare(candidate_version)
        return candidate_version < self.version


class EnpkgUpstreamMatch(_VersionConstraint):
    def __init__(self, upstream_string):
        self.version = EnpkgVersion.from_upstream_and_build(upstream_string, 0)

    def matches(self, candidate_version):
        self._ensure_can_compare(candidate_version)
        return candidate_version.upstream == self.version.upstream
