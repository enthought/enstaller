import sys

from egginst.vendor.six.moves import unittest

from enstaller.errors import InvalidConfiguration
from enstaller.proxy_info import ProxyInfo


class TestProxyInfoFromString(unittest.TestCase):
    def test_without_host(self):
        # Given
        s = ""

        # When/Then
        with self.assertRaises(InvalidConfiguration):
            ProxyInfo.from_string(s)

        # Given
        s = ":3128"

        # When/Then
        with self.assertRaises(InvalidConfiguration):
            ProxyInfo.from_string(s)

    @unittest.skipIf(sys.version_info < (2, 7),
                     "Bug in stdlib on 2.6")
    def test_without_scheme(self):
        # Given
        s = "acme.com:3129"

        # When
        info = ProxyInfo.from_string(s)

        # Then
        self.assertEqual(info.scheme, "http")
        self.assertEqual(info.host, "acme.com")
        self.assertEqual(info.user, "")
        self.assertEqual(info.password, "")
        self.assertEqual(info.port, 3129)

    def test_simple(self):
        # Given
        s = "http://acme.com"

        # When
        info = ProxyInfo.from_string(s)

        # Then
        self.assertEqual(info.scheme, "http")
        self.assertEqual(info.user, "")
        self.assertEqual(info.password, "")
        self.assertEqual(info.port, 3128)

    def test_simple_port(self):
        # Given
        s = "http://acme.com:3129"

        # When
        info = ProxyInfo.from_string(s)

        # Then
        self.assertEqual(info.scheme, "http")
        self.assertEqual(info.user, "")
        self.assertEqual(info.password, "")
        self.assertEqual(info.port, 3129)

    def test_simple_user(self):
        # Given
        s = "http://john:doe@acme.com"

        # When
        info = ProxyInfo.from_string(s)

        # Then
        self.assertEqual(info.scheme, "http")
        self.assertEqual(info.user, "john")
        self.assertEqual(info.password, "doe")
        self.assertEqual(info.port, 3128)

    def test_simple_user_wo_password(self):
        # Given
        s = "http://john@acme.com"

        # When
        info = ProxyInfo.from_string(s)

        # Then
        self.assertEqual(info.scheme, "http")
        self.assertEqual(info.user, "john")
        self.assertEqual(info.password, "")
        self.assertEqual(info.port, 3128)

    def test_scheme(self):
        # Given
        s = "https://john@acme.com"

        # When
        info = ProxyInfo.from_string(s)

        # Then
        self.assertEqual(info.scheme, "https")
        self.assertEqual(info.user, "john")
        self.assertEqual(info.password, "")
        self.assertEqual(info.port, 3128)


class TestProxyInfo(unittest.TestCase):
    def test_no_user(self):
        with self.assertRaises(InvalidConfiguration):
            ProxyInfo("acme.com", password="yoyo")

    def test_str_simple(self):
        # Given
        proxy_info = ProxyInfo.from_string("http://acme.com:3129")

        # When
        s = str(proxy_info)

        # Then
        self.assertEqual(s, "http://acme.com:3129")

    def test_str_full(self):
        # Given
        proxy_info = ProxyInfo.from_string("http://john:doe@acme.com:3129")

        # When
        s = str(proxy_info)

        # Then
        self.assertEqual(s, "http://john:doe@acme.com:3129")
