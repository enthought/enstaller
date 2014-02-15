import sys
import urllib2

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from egginst.testing_utils import ControlledEnv
from enstaller.errors import InvalidConfiguration
from enstaller.proxy.util import get_proxy_info, get_proxystr, \
    install_proxy_handlers, setup_proxy


PROXY_HOST = "PROXY_HOST"
PROXY_PORT = "PROXY_PORT"
PROXY_USER = "PROXY_USER"
PROXY_PASS = "PROXY_PASS"

_IGNORED_KEYS = [PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS]

class TestGetProxyInfo(unittest.TestCase):
    @mock.patch("enstaller.proxy.util.os.environ", ControlledEnv(_IGNORED_KEYS))
    def test_from_string(self):
        self.assertEqual(get_proxy_info("http://acme.com"),
                         {"host": "http://acme.com", "port": 80, "user": None,
                          "pass": None})
        self.assertEqual(get_proxy_info("http://acme.com:8080"),
                         {"host": "http://acme.com", "port": 8080, "user": None,
                          "pass": None})
        self.assertEqual(get_proxy_info("http://john:doe@acme.com:8080"),
                         {"host": "http://acme.com", "port": 8080, "user": "john",
                          "pass": "doe"})
        self.assertEqual(get_proxy_info("acme.com:8080"),
                         {"host": "http://acme.com", "port": 8080, "user": None,
                          "pass": None})


    def test_from_empty_string(self):
        with mock.patch("enstaller.proxy.util.os.environ", ControlledEnv(_IGNORED_KEYS)):
            with self.assertRaises(InvalidConfiguration):
                get_proxy_info("")

        env = ControlledEnv()
        env[PROXY_USER] = "john"
        env[PROXY_PASS] = "doe"
        env[PROXY_HOST] = "http://acme.com"
        env[PROXY_PORT] = "3128"

        self.assertEqual(get_proxy_info(),
                         {"host": "http://acme.com", "port": 3128,
                          "user": "john", "pass": "doe"})

class TestGetProxyStr(unittest.TestCase):
    @unittest.expectedFailure
    def test_simple_with_scheme(self):
        pinfo = {"host": "http://acme.com", "user": "john", "pass": "doe", "port": 8080}

        self.assertEqual(get_proxystr(pinfo), "http://john:doe@acme.com:8080")

    @unittest.expectedFailure
    def test_empty_pinfo(self):
        pinfo = {}
        self.assertEqual(get_proxystr(pinfo), "")

    def test_simple_without_scheme(self):
        pinfo = {"host": "acme.com", "user": "john", "pass": "doe", "port": 8080}
        self.assertEqual(get_proxystr(pinfo), "john:doe@acme.com:8080")

        pinfo = {"host": "acme.com", "port": 8080}
        self.assertEqual(get_proxystr(pinfo), "acme.com:8080")

class OpenerMatcher(object):
    """
    Clumsy class to match urllib2.install_opener argument against a set of
    proxies.

    Parameters
    ----------
    proxies: dict
        The dict of proxies expected in ProxyHandler.proxies attribute.
    """
    def __init__(self, proxies):
        self.proxies = proxies

    def __eq__(self, other):
        def _find_proxy_handler():
            return [handler for handler in other.handlers \
                    if isinstance(handler, urllib2.ProxyHandler)]
        proxy_handlers = _find_proxy_handler()
        if len(proxy_handlers) < 1:
            return False
        else:
            for handler in proxy_handlers:
                if handler.proxies == self.proxies:
                    return True
            return False

class TestProxySetup(unittest.TestCase):
    @mock.patch("os.environ", ControlledEnv(_IGNORED_KEYS))
    def test_install_proxy_handlers_simple(self):
        with mock.patch("urllib2.install_opener") as mocked:
            pinfo = {"host": "acme.com", "user": "john", "pass": "doe",
                     "port": 8080}
            install_proxy_handlers(pinfo)

            self.assertTrue(mocked.called)

            proxies = {"http": "john:doe@acme.com:8080",
                       "https": "john:doe@acme.com:8080"}
            mocked.assert_called_with(OpenerMatcher(proxies))

    @mock.patch("os.environ", ControlledEnv(_IGNORED_KEYS))
    def test_setup_proxy_simple(self):
        with mock.patch("urllib2.install_opener") as mocked:
            proxystr = "http://acme.com:8080"
            installed = setup_proxy(proxystr)

            self.assertTrue(installed)
            self.assertTrue(mocked.called)

            proxies = {"http": "http://acme.com:8080",
                       "https": "http://acme.com:8080"}
            mocked.assert_called_with(OpenerMatcher(proxies))

    @mock.patch("os.environ", ControlledEnv(_IGNORED_KEYS))
    def test_setup_proxy_empty_host(self):
        with mock.patch("urllib2.install_opener"):
            with self.assertRaises(InvalidConfiguration):
                setup_proxy("")
