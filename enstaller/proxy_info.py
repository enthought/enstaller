import urllib2
import urlparse

from enstaller.errors import InvalidConfiguration


_DEFAULT_PORT = 3128


class ProxyInfo(object):
    @classmethod
    def from_string(cls, s):
        parts = urlparse.urlparse(s)
        scheme = parts.scheme
        userpass, hostport = urllib2.splituser(parts.netloc)
        if userpass is None:
            user, password = "", ""
        else:
            user, password = urllib2.splitpasswd(userpass)
        host, port = urllib2.splitport(hostport)
        if port is None:
            port = _DEFAULT_PORT
        else:
            port = int(port)
        return cls(host, scheme, port, user, password)

    def __init__(self, host, scheme="http", port=_DEFAULT_PORT, user=None,
                 password=None):
        self.host = host
        self.scheme = scheme
        self.port = port
        self.user = user or ""
        self.password = password or ""

        if self.password and not self.user:
            msg = "One cannot create a proxy setting with a password but " \
                  "without a user "
            raise InvalidConfiguration(msg)

    def __str__(self):
        netloc = "{0}:{1}".format(self.host, self.port)

        if self.user:
            netloc = "{0}:{1}@{2}".format(self.user, self.password, netloc)

        return urlparse.urlunparse((self.scheme, netloc, "", "", "", ""))
