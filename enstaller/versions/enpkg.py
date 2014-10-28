from .pep386_workaround import PEP386WorkaroundVersion


class EnpkgVersion(object):
    @classmethod
    def from_upstream_and_build(cls, upstream, build):
        """ Creates a new EnpkgVersion from the upstream string and the
        build number.

        Parameters
        ----------
        upstream : str
            The upstream version (e.g. '1.3.0')
        build : int
            The build number
        """
        return cls.from_string("{0}-{1}".format(upstream, build))

    @classmethod
    def from_string(cls, version_string):
        """ Creates a new EnpkgVersion from its string representation.

        Parameters
        ----------
        version_string : str
            the version string.
        """
        parts = version_string.rsplit("-")
        if len(parts) < 2:
            msg = "Invalid version format: {0!r}".format(version_string)
            raise ValueError(msg)
        
        upstream = PEP386WorkaroundVersion.from_string(parts[0])
        try:
            build = int(parts[1])
        except ValueError:
            raise ValueError("Invalid build number: {0!r}".format(parts[1]))

        return cls(upstream, build)

    def __init__(self, upstream, build):
        """ Creates a new EnpkgVersion instance

        Parameters
        ----------
        upstream : PEP386WorkaroundVersion
            The upstream version
        build : int
            The build number
        """
        self.upstream = upstream
        self.build = build

        self._parts = upstream, build

    def __str__(self):
        return str(self.upstream) + "-" + str(self.build)

    def _cannot_compare(self, other):
        msg = "Cannot compare {0!r} and {1!r}"
        raise TypeError(msg.format(type(self), type(other)))

    def __eq__(self, other):
        if not isinstance(other, EnpkgVersion):
            self._cannot_compare(other)
        return self._parts == other._parts

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if not isinstance(other, EnpkgVersion):
            self._cannot_compare(other)
        return self._parts < other._parts

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __gt__(self, other):
        if not isinstance(other, EnpkgVersion):
            self._cannot_compare(other)
        return self._parts > other._parts

    def __ge__(self, other):
        return self.__gt__(other) or self.__eq__(other)
