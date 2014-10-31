from __future__ import absolute_import

import base64

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
            return tuple(parts)
        else:
            raise InvalidConfiguration("Invalid auth line")

    def __init__(self, username, password):
        self.username = username
        self.password = password

    @property
    def request_adapter(self):
        return (self.username, self.password)

    def __eq__(self, other):
        return self.__class__ == other.__class__ \
            and self.username == other.username \
            and self.password == other.password
