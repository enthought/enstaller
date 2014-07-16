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
    pass

class EnpkgError(EnstallerException):
    # FIXME: why is this a class-level attribute ?
    req = None

class MissingPackage(EnstallerException):
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

EXIT_ABORTED = 130
