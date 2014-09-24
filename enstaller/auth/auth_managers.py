from __future__ import absolute_import

import abc

from egginst._compat import urlparse, with_metaclass
from enstaller.errors import AuthFailedError, EnstallerException
from enstaller.vendor import requests

from .user_info import UserInfo


class IAuthManager(with_metaclass(abc.ABCMeta)):
    @abc.abstractproperty
    def auth(self):
        """ A (username, password) pair. Only valid once authenticated.
        """

    @abc.abstractproperty
    def authenticate(self):
        """ Authenticate.

        If successfull, the auth property is sets up

        Parameters
        ----------
        session : Session
            The connection handled used to manage http connections(s).

        Returns
        -------
        a UserInfo object.
        """


class LegacyCanopyAuthManager(object):
    def __init__(self, url, auth):
        self.url = url
        self._raw_auth = auth
        self._auth = None

    @property
    def auth(self):
        return self._auth

    def authenticate(self, session):
        try:
            resp = session.get(self.url, auth=self._raw_auth)
        except requests.exceptions.ConnectionError as e:
            raise AuthFailedError(e)

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise AuthFailedError("Authentication error: %r" % str(e))

        # See if web API refused to authenticate
        user = UserInfo.from_json_string(resp.content.decode("utf8"))
        if not user.is_authenticated:
            msg = 'Authentication error: Invalid user login.'
            raise AuthFailedError(msg)

        self._auth = self._raw_auth
        return user


class OldRepoAuthManager(object):
    def __init__(self, index_urls, auth):
        self.index_urls = index_urls
        self._raw_auth = auth
        self._auth = None

    @property
    def auth(self):
        return self._auth

    def authenticate(self, session):
        for index_url, _ in self.index_urls:
            parse = urlparse.urlparse(index_url)
            if parse.scheme in ("http", "https"):
                resp = session.head(index_url, auth=self.auth)
                try:
                    resp.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    http_code = resp.status_code
                    if http_code in (401, 403):
                        msg = "Authentication error: {0!r}".format(str(e))
                        raise AuthFailedError(msg)
                    elif http_code == 404:
                        msg = "Could not access repo {0!r} (error: {1!r})". \
                              format(index_url, str(e))
                        raise AuthFailedError(msg)
                    else:
                        raise AuthFailedError(str(e))
        user = UserInfo(is_authenticated=True)
        self._auth = self._raw_auth
        return UserInfo(is_authenticated=True)


IAuthManager.register(LegacyCanopyAuthManager)
IAuthManager.register(OldRepoAuthManager)
