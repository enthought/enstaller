from egginst._compat import splitpasswd, splitport, splituser, urlparse

from enstaller.errors import InvalidConfiguration


_DEFAULT_PORT = 3128


class ProxyInfo(object):
    @classmethod
    def from_string(cls, s):
        parts = urlparse.urlparse(s)
        scheme = parts.scheme
        userpass, hostport = splituser(parts.netloc)
        if userpass is None:
            user, password = "", ""
        else:
            user, password = splitpasswd(userpass)
        host, port = splitport(hostport)
        if port is None:
            port = _DEFAULT_PORT
        else:
            port = int(port)
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

        return urlparse.urlunparse((self.scheme, netloc, "", "", "", ""))

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
