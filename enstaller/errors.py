class EnstallerException(Exception):
    pass

class InvalidPythonPathConfiguration(EnstallerException):
    pass

class InvalidConfiguration(EnstallerException):
    pass

class InvalidFormat(InvalidConfiguration):
    pass

class AuthFailedError(EnstallerException):
    pass

class EnpkgError(EnstallerException):
    # FIXME: why is this a class-level attribute ?
    req = None

EXIT_ABORTED = 130
