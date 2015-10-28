# FIXME: those are in egginst to avoid egginst<->enstaller circular import
class EnstallerException(Exception):
    pass


class InvalidChecksum(EnstallerException):
    def __init__(self, filename, expected_checksum, actual_checksum):
        template = "Checksum mismatch for {0!r}: received {1!r} " \
                   "(expected {2!r})"
        self.msg = template.format(filename, actual_checksum,
                                   expected_checksum)

    def __str__(self):
        return self.msg


class InvalidMetadata(EnstallerException):
    pass


class ProcessCommunicationError(EnstallerException):
    pass


class ConnectionError(EnstallerException):
    pass


class InvalidPythonPathConfiguration(EnstallerException):
    pass


class InvalidConfiguration(EnstallerException):
    pass


class InvalidFormat(InvalidConfiguration):
    def __init__(self, message, lineno=None, col_offset=None):
        self.message = message
        self.lineno = lineno
        self.col_offset = col_offset

    def __str__(self):
        return self.message


class AuthFailedError(EnstallerException):
    def __init__(self, *args):
        super(AuthFailedError, self).__init__(*args)
        if len(args) > 1:
            self.original_exception = args[1]
        else:
            self.original_exception = None


class EnpkgError(EnstallerException):
    pass


class NoSuchPackage(EnstallerException):
    pass


class SolverException(EnstallerException):
    pass


class NoPackageFound(SolverException):
    """Exception thrown if no egg can be found for the given requirement."""

    def __init__(self, requirement, *a, **kw):
        self.requirement = requirement
        super(NoPackageFound, self).__init__(*a, **kw)


class UnavailablePackage(SolverException):
    """Exception thrown when a package is not available for a given
    subscription level."""

    def __init__(self, requirement, *a, **kw):
        self.requirement = requirement
        super(UnavailablePackage, self).__init__(*a, **kw)


class NotInstalledPackage(SolverException):
    """Exception thrown when trying to remove a non installed package.
    subscription level."""

    def __init__(self, requirement, *a, **kw):
        self.requirement = requirement
        super(NotInstalledPackage, self).__init__(*a, **kw)


class MissingDependency(SolverException):
    """Exception thrown when a dependency for package is not available."""

    def __init__(self, requester, requirement, *a, **kw):
        self.requester = requester
        self.requirement = requirement
        super(MissingDependency, self).__init__(*a, **kw)


EXIT_ABORTED = 130
