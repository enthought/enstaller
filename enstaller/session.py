from enstaller.vendor import requests


class Session(object):
    """ Simple class to handle http session management

    It also ensures connection settings such as proxy, SSL CA certification,
    etc... are handled consistently).

    Parameters
    ----------
    authenticator : IAuthManager
        An authenticator instance
    cache_directory : str
        A writeable directory to cache data and eggs.
    proxies : dict
        A proxy dict as expected by requests (and provided by
        Configuration.proxy_dict).
    verify : bool
        If True, SSL CA are verified (default).
    """
    def __init__(self, authenticator, cache_directory, proxies=None, verify=True):
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

    def fetch(self, url):
        resp = self._session.get(url, stream=True)
        resp.raise_for_status()
        return resp

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
