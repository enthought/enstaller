from enstaller.vendor.requests import Session


class ConnectionHandler(object):
    """ Simple class to handle http requests configuration (proxy, ssl
    certification settings, etc...)
    """
    def __init__(self, proxies=None, verify=True):
        self.proxies = proxies
        self.verify = verify

        self._session = Session()

    def get(self, url, auth=None):
        return self._session.get(url, auth=auth, proxies=self.proxies,
                                 verify=self.verify)

    def head(self, url, auth=None):
        return self._session.head(url, auth=auth, proxies=self.proxies,
                                  verify=self.verify)
