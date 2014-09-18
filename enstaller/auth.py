import json
import urlparse

from enstaller.errors import AuthFailedError, EnstallerException
from enstaller.vendor import requests


_INDEX_NAME = "index.json"


class UserInfo(object):
    @classmethod
    def from_json_string(cls, s):
        return cls.from_json(json.loads(s))

    @classmethod
    def from_json(cls, json_data):
        return cls(json_data["is_authenticated"],
                   json_data["first_name"],
                   json_data["last_name"],
                   json_data["has_subscription"],
                   json_data["subscription_level"])

    def __init__(self, is_authenticated, first_name="", last_name="",
                 has_subscription=False, subscription_level="free"):
        self.is_authenticated = is_authenticated
        self.first_name = first_name
        self.last_name = last_name
        self.has_subscription = has_subscription
        self._subscription_level = subscription_level

    @property
    def subscription_level(self):
        if self.is_authenticated and self.has_subscription:
            return 'Canopy / EPD Basic or above'
        elif self.is_authenticated and not self.has_subscription:
            return 'Canopy / EPD Free'
        else:
            return None

    def to_dict(self):
        keys = (
             "is_authenticated",
             "first_name",
             "last_name",
             "has_subscription",
             "subscription_level",
        )
        return dict((k, getattr(self, k)) for k in keys)

    def __eq__(self, other):
        return self.to_dict() == other.to_dict()


DUMMY_USER = UserInfo(False)


def authenticate(configuration, verify=True):
    """
    Attempt to authenticate the user's credentials by the appropriate
    means.

    Parameters
    ----------
    configuration : Configuration_like
        A Configuration instance. The authentication information need to be set
        up.
    verify : bool
	If False, do not verify SSL certificate when authenticating (unsecure).

    Returns
    -------
    user_info : UserInfo

    If the 'use_webservice' mode is enabled in the configuration, authenticate
    with the web API and return the corresponding information.

    Else, authenticate with the configured repositories in
    config.indexed_repositories

    If authentication fails, raise an exception.
    """
    if not configuration.is_auth_configured:
        raise EnstallerException("No valid auth information in "
                                 "configuration, cannot authenticate.")

    auth = configuration.auth

    if configuration.use_webservice:
        # check credentials using web API
        user = _web_auth(auth, configuration.api_url, configuration.proxy_dict,
                         verify=verify)
        if not user.is_authenticated:
            raise AuthFailedError('Authentication failed: could not authenticate')
    else:
        for index_url, __ in configuration.indices:
            parse = urlparse.urlparse(index_url)
            if parse.scheme in ("http", "https"):
                resp = requests.head(index_url, auth=auth,
                                     proxies=configuration.proxy_dict)
                try:
                    resp.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    http_code = resp.status_code
                    if http_code in (401, 403):
                        msg = "Authentication error: {0!r}".format(e.message)
                        raise AuthFailedError(msg)
                    elif http_code == 404:
                        msg = "Could not access repo {0!r} (error: {1!r})". \
                              format(index_url, e.message)
                        raise AuthFailedError(msg)
                    else:
                        raise
        user = UserInfo(is_authenticated=True)

    return user


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


def _web_auth(auth, api_url, proxies=None, verify=True):
    """
    Authenticate a user's credentials (an `auth` tuple of username, password)
    using the web API.
    """
    if proxies is None:
        proxies = {}
    # Make basic local checks
    username, password = auth
    if username is None or password is None:
        raise AuthFailedError("Authentication error: User login is required.")

    try:
        resp = requests.get(api_url, auth=auth, proxies=proxies, verify=verify)
    except requests.exceptions.ConnectionError as e:
        raise AuthFailedError(e)
    else:
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise AuthFailedError("Authentication error: %r" % str(e))
        else:
            # See if web API refused to authenticate
            user = UserInfo.from_json_string(resp.content)
            if not user.is_authenticated:
                msg = 'Authentication error: Invalid user login.'
                raise AuthFailedError(msg)
            return user
