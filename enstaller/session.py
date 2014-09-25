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

    @property
    def user_info(self):
        return self._authenticator.user_info

    def authenticate(self, auth):
        self._authenticator.authenticate(self, auth)
        self._session.auth = auth

    def get(self, url):
        return self._session.get(url, proxies=self.proxies, verify=self.verify)

    def head(self, url):
        return self._session.head(url, proxies=self.proxies,
                                  verify=self.verify)

    def _raw_get(self, url, auth=None):
        return self._session.get(url, auth=auth, proxies=self.proxies,
                                 verify=self.verify)

    def _raw_head(self, url, auth=None):
        return self._session.head(url, auth=auth, proxies=self.proxies,
                                  verify=self.verify)

    def _raw_post(self, url, auth=None):
        return self._session.post(url, auth=auth, proxies=self.proxies,
                                  verify=self.verify)
