from enstaller.vendor import requests


class Session(object):
    """ Simple class to handle http requests configuration (proxy, ssl
    certification settings, etc...) as well as various authentication schemas.
    """
    def __init__(self, proxies=None, verify=True):
        self.proxies = proxies
        self.verify = verify

        self._session = requests.Session()

    def get(self, url, auth=None):
        return self._session.get(url, auth=auth, proxies=self.proxies,
                                 verify=self.verify)

    def head(self, url, auth=None):
        return self._session.head(url, auth=auth, proxies=self.proxies,
                                  verify=self.verify)
