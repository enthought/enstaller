from enstaller.vendor import requests


class Session(object):
    """ Simple class to handle http requests configuration (proxy, ssl
    certification settings, etc...) as well as various authentication schemas.
    """
    def __init__(self, authenticator, proxies=None, verify=True):
        self.proxies = proxies
        self.verify = verify

        self._authenticator = authenticator
        self._session = requests.Session()
        if proxies is not None:
            self._session.proxies = proxies
        self._session.verify = verify

    @property
    def user_info(self):
        return self._authenticator.user_info

    def authenticate(self, auth):
        self._authenticator.authenticate(self, auth)
        self._session.auth = auth

    def get(self, url):
        return self._session.get(url)

    def head(self, url):
        return self._session.head(url)

    def _raw_get(self, url, auth=None):
        return self._session.get(url, auth=auth)

    def _raw_head(self, url, auth=None):
        return self._session.head(url, auth=auth)

    def _raw_post(self, url, auth=None):
        return self._session.post(url, auth=auth)
