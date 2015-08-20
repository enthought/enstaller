from __future__ import absolute_import

import abc

import requests

from egginst._compat import urlparse, with_metaclass

from enstaller.errors import AuthFailedError

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
        resp = session.get(self.url, auth=auth)
        if resp.status_code == 401:
            raise AuthFailedError("Invalid credentials.")
        elif resp.status_code == 200:
            user = UserInfo.from_json_string(resp.content.decode("utf8"))
            if not user.is_authenticated:
                msg = 'Invalid user login.'
                raise AuthFailedError(msg)

            self._auth = auth
        else:
            resp.raise_for_status()


class OldRepoAuthManager(object):
    @classmethod
    def from_configuration(cls, configuration):
        """ Create a OldRepoAuthManager instance from an enstaller config
        object.
        """
        index_urls = tuple(
            repository_info.index_url
            for repository_info in configuration.repositories
        )
        return cls(index_urls)

    def __init__(self, index_urls):
        self.index_urls = index_urls
        self._auth = None

    def authenticate(self, session, auth):
        for index_url in self.index_urls:
            parse = urlparse(index_url)
            if parse.scheme in ("http", "https"):
                resp = session.head(index_url, auth=auth)

                try:
                    resp.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    http_code = resp.status_code
                    if http_code in (401, 403):
                        msg = "Invalid credentials"
                        raise AuthFailedError(msg)
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
        resp = session.post(url, auth=auth)

        if resp.status_code == 401:
            raise AuthFailedError("Invalid credentials.")
        elif resp.status_code == 200:
            token = resp.json()["token"]
            self._auth = BroodBearerTokenAuth(token)
        else:
            resp.raise_for_status()


IAuthManager.register(LegacyCanopyAuthManager)
IAuthManager.register(OldRepoAuthManager)
IAuthManager.register(BroodAuthenticator)
