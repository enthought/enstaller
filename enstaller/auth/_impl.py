from __future__ import absolute_import

import base64
import re
import textwrap

from enstaller.errors import InvalidConfiguration


AUTH_KIND_CLEAR = "auth_clear"


def subscription_message(config, user):
    """
    Return a 'subscription level' message based on the `user`
    information.

    Parameters
    ----------
    config : Configuration
    user : UserInfo

    Returns
    -------
    message : str
        The subscription message.
    """
    message = ""

    if user.is_authenticated:
        if isinstance(config.auth, UserPasswordAuth):
            login = "You are logged in as %s" % config.auth.username
        else:
            login = "You are logged in with an API token"
        subscription = "Subscription level: %s" % user.subscription_level
        name = user.first_name + ' ' + user.last_name
        name = name.strip()
        if name:
            name = ' (' + name + ')'
        message = login + name + '.\n' + subscription
    else:
        message = "You are not logged in.  To log in, type 'enpkg --userpass'."

    return message


class UserPasswordAuth(object):
    @classmethod
    def from_encoded_auth(cls, encoded_auth):
        parts = base64.decodestring(encoded_auth.encode("utf8")). \
            decode("utf8"). \
            split(":")
        if len(parts) == 2:
            return cls(*parts)
        else:
            raise InvalidConfiguration("Invalid auth line")

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def change_auth(self, filename):
        pat = re.compile(r'^(EPD_auth|EPD_username)\s*=.*$', re.M)
        with open(filename, 'r') as fi:
            data = fi.read()

        if not self._is_auth_configured:
            if pat.search(data):
                data = pat.sub("", data)
            with open(filename, 'w') as fo:
                fo.write(data)
            return

        authline = 'EPD_auth = \'%s\'' % self._encoded_auth

        if pat.search(data):
            data = pat.sub(authline, data)
        else:
            lines = data.splitlines()
            lines.append(authline)
            data = '\n'.join(lines) + '\n'

        with open(filename, 'w') as fo:
            fo.write(data)

    @property
    def config_string(self):
        if self.username and self.password:
            authline = 'EPD_auth = %r' % self._encoded_auth
            auth_section = textwrap.dedent("""
            # A Canopy / EPD subscriber authentication is required to access the
            # Canopy / EPD repository.  To change your credentials, use the 'enpkg
            # --userpass' command, which will ask you for your email address
            # password.
            %s
            """ % authline)
        else:
            auth_section = ''
        return auth_section

    @property
    def request_adapter(self):
        return (self.username, self.password)

    # ------------------
    # Private properties
    # ------------------
    @property
    def _encoded_auth(self):
        """
        Auth information, encoded as expected by EPD_auth.
        """
        if not self._is_auth_configured:
            raise InvalidConfiguration("EPD_auth is not available when "
                                       "auth has not been configured.")
        return _encode_auth(self.username, self.password)

    @property
    def _is_auth_configured(self):
        if self.username and self.password is not None:
            return True
        else:
            return False

    def __eq__(self, other):
        return self.__class__ == other.__class__ \
            and self.username == other.username \
            and self.password == other.password


def _encode_string_base64(s):
    return base64.encodestring(s.encode("utf8")).decode("utf8")


def _encode_auth(username, password):
    s = "{0}:{1}".format(username, password)
    return _encode_string_base64(s).rstrip()


