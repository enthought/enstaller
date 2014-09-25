from __future__ import absolute_import

import abc

from egginst._compat import urlparse, with_metaclass
from enstaller.errors import AuthFailedError, EnstallerException
from enstaller.vendor import requests

from .user_info import UserInfo


class IAuthManager(with_metaclass(abc.ABCMeta)):
    @abc.abstractproperty
    def user_info(self):
        """ A UserInfo instance. Only valid once authenticated.

        Will be cached, and raise an RuntimeError if not authenticated
        """

    @abc.abstractproperty
    def authenticate(self, session, auth):
        """ Authenticate.

        If successfull, the auth property is sets up

        Parameters
        ----------
        session : Session
            The connection handled used to manage http connections(s).
        auth : tuple
            The (username, password) pair for authentication.

        Returns
        -------
        a UserInfo object.
        """


class LegacyCanopyAuthManager(object):
    def __init__(self, url):
        self.url = url
        self._auth = None
        self._user_info = None

    @property
    def user_info(self):
        if self._auth is None:
            raise RuntimeError("Not authenticated yet")
        else:
            return self._user_info

    def authenticate(self, session, auth):
        try:
            resp = session._raw_get(self.url, auth=auth)
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
        else:
            self._user_info = user

        self._auth = auth


class OldRepoAuthManager(object):
    def __init__(self, index_urls):
        self.index_urls = index_urls
        self._auth = None

    @property
    def user_info(self):
        return UserInfo(is_authenticated=True)

    def authenticate(self, session, auth):
        for index_url, _ in self.index_urls:
            parse = urlparse.urlparse(index_url)
            if parse.scheme in ("http", "https"):
                try:
                    resp = session._raw_head(index_url, auth=auth)
                except requests.exceptions.ConnectionError as e:
                    raise AuthFailedError(e)

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
        self._auth = auth


IAuthManager.register(LegacyCanopyAuthManager)
IAuthManager.register(OldRepoAuthManager)
