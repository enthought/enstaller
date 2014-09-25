from __future__ import absolute_import

import json

from egginst._compat import urlparse

from enstaller.errors import AuthFailedError, EnstallerException

from .auth_managers import LegacyCanopyAuthManager, OldRepoAuthManager
from .user_info import UserInfo


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
        username, password = config.auth
        login = "You are logged in as %s" % username
        subscription = "Subscription level: %s" % user.subscription_level
        name = user.first_name + ' ' + user.last_name
        name = name.strip()
        if name:
            name = ' (' + name + ')'
        message = login + name + '.\n' + subscription
    else:
        message = "You are not logged in.  To log in, type 'enpkg --userpass'."

    return message
