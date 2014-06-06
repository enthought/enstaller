import json
import socket
import urllib2
import urlparse

from enstaller.errors import (AuthFailedError, ConnectionError,
                              EnstallerException, InvalidConfiguration)


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


def authenticate(configuration):
    """
    Attempt to authenticate the user's credentials by the appropriate
    means.

    Parameters
    ----------
    configuration : Configuration_like
        A Configuration instance. The authentication information need to be set
        up.

    Returns
    -------
    user_info : UserInfo

    If the 'use_webservice' mode is enabled in the configuration, authenticate
    with the web API and return the corresponding information.

    Else, authenticate with the configured repositories in config.IndexedRepos

    If authentication fails, raise an exception.
    """
    if not configuration.is_auth_configured:
        raise EnstallerException("No valid auth information in "
                                 "configuration, cannot authenticate.")

    auth = configuration.get_auth()

    if configuration.use_webservice:
        # check credentials using web API
        user = _web_auth(auth, configuration.api_url)
        if not user.is_authenticated:
            raise AuthFailedError('Authentication failed: could not authenticate')
    else:
        for url in configuration.IndexedRepos:
            parse = urlparse.urlparse(url)
            if parse.scheme in ("http", "https"):
                index = url + _INDEX_NAME
                try:
                    _head_request(index, auth)
                except urllib2.HTTPError as e:
                    http_code = e.getcode()
                    # Python 2.6 compat: HTTPError.reason not available there
                    reason = getattr(e, "reason", "Unkown")
                    if http_code in (401, 403):
                        msg = "Authentication error: {0!r}".format(reason)
                        raise AuthFailedError(msg)
                    elif http_code == 404:
                        msg = "Could not access repo {0!r} (error: {1!r})". \
                              format(index, e.msg)
                        raise InvalidConfiguration(msg)
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
        username, password = config.get_auth()
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


def _web_auth(auth, api_url):
    """
    Authenticate a user's credentials (an `auth` tuple of username, password)
    using the web API.
    """
    # Make basic local checks
    username, password = auth
    if username is None or password is None:
        raise AuthFailedError("Authentication error: User login is required.")

    # Authenticate with the web API
    auth = 'Basic ' + (':'.join(auth).encode('base64').strip())
    req = urllib2.Request(api_url, headers={'Authorization': auth})

    try:
        f = urllib2.urlopen(req)
    except urllib2.URLError as e:
        if isinstance(e.reason, socket.gaierror):
            msg = "could not connect to {0!r}".format(api_url)
            raise ConnectionError(msg)
        else:
            msg = e.reason
            raise AuthFailedError("Authentication error ({0!r})".format(msg))

    try:
        res = f.read()
    except urllib2.HTTPError as e:
        raise AuthFailedError("Authentication error: %s" % e.reason)

    # See if web API refused to authenticate
    user = UserInfo.from_json_string(res)
    if not user.is_authenticated:
        raise AuthFailedError('Authentication error: Invalid user login.')

    return user


def _head_request(url, auth=None):
    if auth:
        auth = 'Basic ' + (':'.join(auth).encode('base64').strip())
        request = urllib2.Request(url)
        request.add_unredirected_header("Authorization", auth)
    else:
        request = urllib2.Request(url)
    request.get_method = lambda: 'HEAD'

    return urllib2.urlopen(request)
