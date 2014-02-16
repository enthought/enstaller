class EnpkgException(Exception):
    pass

class InvalidConfiguration(EnpkgException):
    pass

class AuthFailedError(EnpkgException):
    pass
