from .pep386 import IrrationalVersionError, NormalizedVersion


def normalize_version_string(version_string):
    """
    Normalize the given version string to a string that can be converted to
    a NormalizedVersion.

    This function applies various special cases needed for EPD/Canopy and not
    handled in NormalizedVersion parser.

    Parameters
    ----------
    version_string: str
        The version to convert

    Returns
    -------
    normalized_version: str
        The normalized version string. Note that this is not guaranteed to be
        convertible to a NormalizedVersion
    """
    # This hack makes it possible to use 'rc' in the version, where
    # 'rc' must be followed by a single digit.
    version_string = version_string.replace('rc', '.dev99999')
    # This hack allows us to deal with single number versions (e.g.
    # pywin32's style '214').
    if not "." in version_string:
        version_string += ".0"

    if version_string.endswith(".dev"):
        version_string += "1"
    return version_string


class PEP386WorkaroundVersion(object):
    """A version class that supports comparison, with an escape for
    versions not compatible with PEP386.

    When comparing two versions, 3 cases arise:

        * both are valid: we use the PEP386 comparison algo
        * both are invalid: we use string comparison
        * exactly one of them is valid: the valid one is always considered
          to be greather than the invalid one
    """
    @classmethod
    def from_string(cls, s):
        try:
            normalized = normalize_version_string(s)
            version = NormalizedVersion(normalized,
                                        error_on_huge_major_num=False)
            parts = version.parts
            return cls(parts)
        except IrrationalVersionError:
            parts = s.split(".")
            return cls(parts, is_worked_around=True)

    def __init__(self, parts, is_worked_around=False):
        self._parts = parts

        comparable_parts = []

        numdot = list(parts[0])
        while len(numdot) > 0 and numdot[-1] == 0:
            numdot.pop()

        comparable_parts = [numdot]
        comparable_parts.extend(parts[1:])

        self._comparable_parts = tuple(comparable_parts)
        self._is_worked_around = is_worked_around

    def __str__(self):
        if self._is_worked_around:
            return ".".join(self._parts)
        else:
            return NormalizedVersion.parts_to_str(self._parts)

    def _cannot_compare(self, other):
        raise TypeError("cannot compare %s and %s"
                        % (type(self).__name__, type(other).__name__))

    def __eq__(self, other):
        if not isinstance(other, PEP386WorkaroundVersion):
            self._cannot_compare(other)
        return self._comparable_parts == other._comparable_parts

    def __ne__(self, other):
        return not self.__eq__(other)

    def __le__(self, other):
        if not isinstance(other, PEP386WorkaroundVersion):
            self._cannot_compare(other)
        if (self._is_worked_around and other._is_worked_around) \
           or (not self._is_worked_around and not other._is_worked_around):
            return self._comparable_parts <= other._comparable_parts
        elif self._is_worked_around:
            return True
        else:
            return False

    def __lt__(self, other):
        return self.__le__(other) and self.__ne__(other)

    def __ge__(self, other):
        return not self.__lt__(other) or self.__eq__(other)

    def __gt__(self, other):
        return not self.__le__(other)
