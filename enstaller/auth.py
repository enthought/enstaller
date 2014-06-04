import json
import urllib2
import urlparse

from enstaller.errors import (AuthFailedError, EnstallerException,
                              InvalidConfiguration)


_INDEX_NAME = "index.json"


def authenticate(configuration):
    """
    Attempt to authenticate the user's credentials by the appropriate
    means.

    If 'use_webservice' is set, authenticate with the web API and return
    a dictionary containing user info on success.

    Else, authenticate with the configured repositories in config.IndexedRepos
    return a dict containing is_authenticated=True on success.

    If authentication fails, raise an exception.
    """
    if not configuration.is_auth_configured:
        raise EnstallerException("No valid auth information in "
                                 "configuration, cannot authenticate.")

    user = {}
    auth = configuration.get_auth()

    if configuration.use_webservice:
        # check credentials using web API
        try:
            user = _web_auth(auth, configuration.api_url)
            assert user['is_authenticated']
        except Exception as e:
            raise AuthFailedError('Authentication failed: %s.' % e)
    else:
        for url in configuration.IndexedRepos:
            parse = urlparse.urlparse(url)
            if parse.scheme in ("http", "https"):
                index = url + _INDEX_NAME
                try:
                    _head_request(index, auth)
                except urllib2.HTTPError as e:
                    http_code = e.getcode()
                    if http_code in (401, 403):
                        msg = "Authentication error: {0!r}".format(e.reason)
                        raise AuthFailedError(msg)
                    elif http_code == 404:
                        msg = "Could not access repo {0!r} (error: {1!r})". \
                                format(index, e.msg)
                        raise InvalidConfiguration(msg)
                    else:
                        raise
        user = dict(is_authenticated=True)

    return user


def subscription_message(config, user):
    """
    Return a 'subscription level' message based on the `user`
    dictionary.

    `user` is a dictionary, probably retrieved from the web API, that
    may contain `is_authenticated`, and `has_subscription`.
    """
    message = ""

    if user.get('is_authenticated', False):
        username, password = config.get_auth()
        login = "You are logged in as %s" % username
        subscription = "Subscription level: %s" % subscription_level(user)
        name = user.get('first_name', '') + ' ' + user.get('last_name', '')
        name = name.strip()
        if name:
            name = ' (' + name + ')'
        message = login + name + '.\n' + subscription
    else:
        message = "You are not logged in.  To log in, type 'enpkg --userpass'."

    return message


def _web_auth(auth, api_url):
    """
    Authenticate a user's credentials (an `auth` tuple of username,
    password) using the web API.  Return a dictionary containing user
    info.

    Function taken from Canopy and modified.
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
        raise AuthFailedError("Authentication error: %s" % e.reason)

    try:
        res = f.read()
    except urllib2.HTTPError as e:
        raise AuthFailedError("Authentication error: %s" % e.reason)

    # See if web API refused to authenticate
    user = json.loads(res)
    if not(user['is_authenticated']):
        raise AuthFailedError('Authentication error: Invalid user login.')

    return user


def subscription_level(user):
    """
    Extract the subscription level from the dictionary (`user`) returned by the
    web API.
    """
    if 'has_subscription' in user:
        if user.get('is_authenticated', False) and user.get('has_subscription', False):
            return 'Canopy / EPD Basic or above'
        elif user.get('is_authenticated', False) and not(user.get('has_subscription', False)):
            return 'Canopy / EPD Free'
        else:
            return None
    else:  # don't know the subscription level
        if user.get('is_authenticated', False):
            return 'Canopy / EPD'
        else:
            return None


def _head_request(url, auth=None):
    if auth:
        auth = 'Basic ' + (':'.join(auth).encode('base64').strip())
        request = urllib2.Request(url)
        request.add_unredirected_header("Authorization", auth)
    else:
        request = urllib2.Request(url)
    request.get_method = lambda : 'HEAD'

    return urllib2.urlopen(request)
