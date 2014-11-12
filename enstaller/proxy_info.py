import re

from egginst.vendor.six.moves import urllib

from enstaller.errors import InvalidConfiguration


_DEFAULT_PORT = 3128
_PORT_PROG_R = re.compile('^(.*):([0-9]+)$')
_PASSWD_PROG_R = re.compile('^([^:]*):(.*)$', re.S)


class ProxyInfo(object):
    @classmethod
    def from_string(cls, s):
        parts = urllib.parse.urlparse(s)
        if len(parts.scheme) > 0:
            scheme = parts.scheme
        else:
            scheme = "http"

        if len(parts.netloc) == 0:
            if len(parts.path) > 0:
                # this is to support url such as 'acme.com:3128'
                netloc = parts.path
            else:
                msg = "Invalid proxy string {0!r} (no host found)".format(s)
                raise InvalidConfiguration(msg)
        else:
            netloc = parts.netloc

        userpass, hostport = urllib.parse.splituser(netloc)
        if userpass is None:
            user, password = "", ""
        else:
            user, password = _splitpasswd(userpass)
        host, port = _splitport(hostport)
        if port is None:
            port = _DEFAULT_PORT
        else:
            port = int(port)

        if len(host) == 0:
            msg = "Invalid proxy string {0!r} (no host found)"
            raise InvalidConfiguration(msg.format(s))

        return cls(host, scheme, port, user, password)

    def __init__(self, host, scheme="http", port=_DEFAULT_PORT, user=None,
                 password=None):
        self._host = host
        self._scheme = scheme
        self._port = port
        self._user = user or ""
        self._password = password or ""

        if self._password and not self._user:
            msg = "One cannot create a proxy setting with a password but " \
                  "without a user "
            raise InvalidConfiguration(msg)

    def __str__(self):
        netloc = "{0}:{1}".format(self.host, self.port)

        if self.user:
            netloc = "{0}:{1}@{2}".format(self.user, self.password, netloc)

        return urllib.parse.urlunparse((self.scheme, netloc, "", "", "", ""))

    @property
    def host(self):
        return self._host

    @property
    def password(self):
        return self._password

    @property
    def port(self):
        return self._port

    @property
    def scheme(self):
        return self._scheme

    @property
    def user(self):
        return self._user


# Looks like those are semi-private function in the stdlib, so we bundle it
# here for 2/3 compat
def _splitport(host):
    match = _PORT_PROG_R.match(host)
    if match:
        return match.group(1, 2)
    else:
        return host, None


def _splitpasswd(user):
    match = _PASSWD_PROG_R.match(user)
    if match:
        return match.group(1, 2)
    else:
        return user, None
