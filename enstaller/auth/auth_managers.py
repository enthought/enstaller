from __future__ import absolute_import

import abc

from egginst._compat import with_metaclass
from egginst.vendor.six.moves import urllib

from enstaller.errors import AuthFailedError
from enstaller.vendor import requests

from .user_info import UserInfo


class IAuthManager(with_metaclass(abc.ABCMeta)):
    @abc.abstractproperty
    def authenticate(self, session, auth):
        """ Authenticate.

        Parameters
        ----------
        session : Session
            The connection handled used to manage http connections(s).
        auth : tuple
            The (username, password) pair for authentication.

        Raises
        ------
        an AuthFailedError if authentication failed.
        """


class LegacyCanopyAuthManager(object):
    @classmethod
    def from_configuration(cls, configuration):
        """ Create a LegacyCanopyAuthManager instance from an enstaller config
        object.
        """
        return cls(configuration.api_url)

    def __init__(self, url):
        self.url = url
        self._auth = None

    def authenticate(self, session, auth):
        try:
            resp = session._raw_get(self.url, auth=auth)
        except requests.exceptions.SSLError as e:
            raise
        except requests.exceptions.ConnectionError as e:
            raise AuthFailedError(str(e), e)

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise AuthFailedError("Authentication error: %r" % str(e), e)

        # See if web API refused to authenticate
        user = UserInfo.from_json_string(resp.content.decode("utf8"))
        if not user.is_authenticated:
            msg = 'Authentication error: Invalid user login.'
            raise AuthFailedError(msg)

        self._auth = auth


class OldRepoAuthManager(object):
    @classmethod
    def from_configuration(cls, configuration):
        """ Create a OldRepoAuthManager instance from an enstaller config
        object.
        """
        return cls(configuration.indices)

    def __init__(self, index_urls):
        self.index_urls = index_urls
        self._auth = None

    def authenticate(self, session, auth):
        for index_url, _ in self.index_urls:
            parse = urllib.parse.urlparse(index_url)
            if parse.scheme in ("http", "https"):
                try:
                    resp = session._raw_head(index_url, auth=auth)
                except requests.exceptions.SSLError as e:
                    raise
                except requests.exceptions.ConnectionError as e:
                    raise AuthFailedError(str(e), e)

                try:
                    resp.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    http_code = resp.status_code
                    if http_code in (401, 403):
                        msg = "Authentication error: {0!r}".format(str(e))
                        raise AuthFailedError(msg, e)
                    elif http_code == 404:
                        msg = "Could not access repo {0!r} (error: {1!r})". \
                              format(index_url, str(e))
                        raise AuthFailedError(msg, e)
                    else:
                        raise AuthFailedError(str(e), e)
        self._auth = auth


class BroodBearerTokenAuth(requests.auth.AuthBase):

    def __init__(self, token):
        self._token = token

    def __call__(self, request):
        request.headers['Authorization'] = 'Bearer {0}'.format(self._token)
        return request


class BroodAuthenticator(object):
    """ Token-based authenticator for brood stores."""
    @classmethod
    def from_configuration(cls, configuration):
        """ Create a BroodAuthenticator instance from an enstaller config
        object.
        """
        return cls(configuration.store_url)

    def __init__(self, url):
        self.url = url
        self._auth = None

    def authenticate(self, session, auth):
        url = self.url + "/api/v0/json/auth/tokens/auth"
        try:
            resp = session._raw_post(url, auth=auth)
        except requests.exceptions.ConnectionError as e:
            raise AuthFailedError(e)

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise AuthFailedError("Authentication error: %r" % str(e))

        token = resp.json()["token"]
        self._auth = BroodBearerTokenAuth(token)


IAuthManager.register(LegacyCanopyAuthManager)
IAuthManager.register(OldRepoAuthManager)
IAuthManager.register(BroodAuthenticator)
