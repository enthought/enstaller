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
    # FIXME: why is this a class-level attribute ?
    req = None


class NoSuchPackage(EnstallerException):
    pass


class SolverException(EnstallerException):
    pass


class NoPackageFound(SolverException):
    """Exception thrown if no egg can be found for the given requirement."""

    def __init__(self, msg, requirement):
        super(NoPackageFound, self).__init__(msg)
        self.requirement = requirement


class UnavailablePackage(EnstallerException):
    """Exception thrown when a package is not available for a given
    subscription level."""

    def __init__(self, requirement):
        self.requirement = requirement


class MissingDependency(SolverException):
    """Exception thrown when a dependency for package is not available."""

    def __init__(self, msg, requester, requirement):
        super(MissingDependency, self).__init__(msg)
        self.requirement = requirement
        self.requester = requester

EXIT_ABORTED = 130
