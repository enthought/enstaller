class EnstallerException(Exception):
    pass

class InvalidChecksum(EnstallerException):
    def __init__(self, filename, expected_checksum, actual_checksum):
        template = "Checksum mismatch for {0!r}: received {1!r} " \
                   "(expected {2!r})"
        self.msg = template.format(filename, actual_checksum,
                                   expected_checksum)

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

class MissingPackage(EnstallerException):
    pass

EXIT_ABORTED = 130
