from __future__ import absolute_import

import abc
import base64
import re
import textwrap

from egginst._compat import with_metaclass
from enstaller.errors import InvalidConfiguration
from enstaller.vendor import requests

from .auth_managers import BroodBearerTokenAuth


_CLEARTEXT_AUTH_R = re.compile(r'^(EPD_auth|EPD_username)\s*=.*$', re.M)
_API_TOKEN_AUTH_R = re.compile(r'^api_token\s*=.*$', re.M)


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
        login = config.auth.logged_message
        subscription = "Subscription level: %s" % user.subscription_level
        name = user.first_name + ' ' + user.last_name
        name = name.strip()
        if name:
            name = ' (' + name + ')'
        message = login + name + '.\n' + subscription
    else:
        message = "You are not logged in.  To log in, type 'enpkg --userpass'."

    return message


class IAuth(with_metaclass(abc.ABCMeta)):
    @abc.abstractmethod
    def change_auth(self, filename):
        """
        Change the auth information in the configuration file.
        """

    @abc.abstractmethod
    def to_config_dict(self):
        """
        Return a dict that can be used for json/yaml serialization.
        """

    @abc.abstractproperty
    def cant_login_message(self):
        """
        Return a string to show when cannot authenticate.
        """

    @abc.abstractproperty
    def config_string(self):
        """
        The text to write in the configuration file for this particular
        auth.
        """

    @abc.abstractproperty
    def logged_message(self):
        """
        The string to print to indicate a user is logged in.
        """

    @abc.abstractproperty
    def request_adapter(self):
        """ Return an object that can be passed to the auth argument of
        requests Session and feunctions.
        """


class UserPasswordAuth(IAuth):
    """ Simple clear text username/password authentication."""
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
        if username is None or username == "":
            msg = "Invalid username: {0!r}".format(username)
            raise InvalidConfiguration(msg)

        self.username = username
        self.password = password

    def change_auth(self, filename):
        with open(filename, 'r') as fi:
            data = fi.read()

        authline = 'EPD_auth = \'%s\'' % self._encoded_auth

        if _API_TOKEN_AUTH_R.search(data):
            data = _API_TOKEN_AUTH_R.sub("", data)

        if _CLEARTEXT_AUTH_R.search(data):
            data = _CLEARTEXT_AUTH_R.sub(authline, data)
        else:
            lines = data.splitlines()
            lines.append(authline)
            data = '\n'.join(lines) + '\n'

        with open(filename, 'w') as fo:
            fo.write(data)

    def to_config_dict(self):
        return {"kind": "simple",
                "username": self.username,
                "password": self.password}

    @property
    def config_string(self):
        authline = "EPD_auth = '%s'" % self._encoded_auth
        auth_section = textwrap.dedent("""
        # A Canopy / EPD subscriber authentication is required to access the
        # Canopy / EPD repository.  To change your credentials, use the 'enpkg
        # --userpass' command, which will ask you for your email address
        # password.
        %s
        """ % authline)
        return auth_section

    @property
    def cant_login_message(self):
        return "Could not authenticate as '{0}'".format(self.username)

    @property
    def logged_message(self):
        return "You are logged in as '{0}'".format(self.username)

    @property
    def request_adapter(self):
        return requests.auth.HTTPBasicAuth(self.username, self.password)

    # ------------------
    # Private properties
    # ------------------
    @property
    def _encoded_auth(self):
        """
        Auth information, encoded as expected by EPD_auth.
        """
        return _encode_auth(self.username, self.password)

    def __eq__(self, other):
        return self.__class__ == other.__class__ \
            and self.username == other.username \
            and self.password == other.password


class APITokenAuth(IAuth):
    def __init__(self, api_token):
        self._api_token = api_token

    def change_auth(self, filename):
        with open(filename, "rt") as fp:
            data = fp.read()

        if _CLEARTEXT_AUTH_R.search(data):
            data = _CLEARTEXT_AUTH_R.sub("", data)

        m = _API_TOKEN_AUTH_R.search(data)
        if m:
            data = _API_TOKEN_AUTH_R.sub(self.config_string, data)
        else:
            lines = data.splitlines()
            lines.append(self.config_string)
            data = "\n".join(lines)

        with open(filename, "wt") as fp:
            fp.write(data)

    def to_config_dict(self):
        return {"kind": "token", "api_token": self.api_token}

    @property
    def cant_login_message(self):
        msg = ("Could not authenticate with the given token: check your token"
               " settings")
        return msg

    @property
    def config_string(self):
        return "api_token = '{0}'".format(self._api_token)

    @property
    def logged_message(self):
        return "logged in using API token"

    @property
    def request_adapter(self):
        return BroodBearerTokenAuth(self._api_token)

    def __eq__(self, other):
        return self.__class__ == other.__class__ \
            and self._api_token == other._api_token


def _encode_string_base64(s):
    return base64.encodestring(s.encode("utf8")).decode("utf8")


def _encode_auth(username, password):
    s = "{0}:{1}".format(username, password)
    return _encode_string_base64(s).rstrip()
