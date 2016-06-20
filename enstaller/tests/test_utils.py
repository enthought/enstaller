from __future__ import print_function

import contextlib
import os.path
import random
import sys

import mock

from egginst.main import name_version_fn
from egginst.tests.common import DUMMY_EGG_SIZE, DUMMY_EGG, \
    DUMMY_EGG_MTIME, DUMMY_EGG_MD5
from egginst.vendor.six.moves import unittest

from enstaller.utils import canonical, comparable_version, input_auth, \
    path_to_uri, uri_to_path, info_file, cleanup_url, \
    prompt_yes_no, under_venv, real_prefix
from .common import mock_input, mock_print, mock_raw_input


class TestUtils(unittest.TestCase):

    def test_canonical(self):
        for name, cname in [
            ('NumPy', 'numpy'),
            ('MySql-python', 'mysql_python'),
            ('Python-dateutil', 'python_dateutil'),
        ]:
            self.assertEqual(canonical(name), cname)

    def test_naming(self):
        for fn, name, ver, cname in [
            ('NumPy-1.5-py2.6-win32.egg', 'NumPy', '1.5-py2.6-win32', 'numpy'),
            ('NumPy-1.5-2.egg', 'NumPy', '1.5-2', 'numpy'),
            ('NumPy-1.5.egg', 'NumPy', '1.5', 'numpy'),
        ]:
            self.assertEqual(name_version_fn(fn), (name, ver))
            self.assertEqual(name.lower(), cname)
            self.assertEqual(canonical(name), cname)

    def test_comparable_version(self):
        for versions in (
            ['1.0.4', '1.2.1', '1.3.0b1', '1.3.0', '1.3.10',
             '1.3.11.dev7', '1.3.11.dev12', '1.3.11.dev111',
             '1.3.11', '1.3.143',
             '1.4.0.dev7749', '1.4.0rc1', '1.4.0rc2', '1.4.0'],
            ['2008j', '2008k', '2009b', '2009h', '2010b'],
            ['0.99', '1.0a2', '1.0b1', '1.0rc1', '1.0', '1.0.1'],
            ['2.0.8', '2.0.10', '2.0.10.1', '2.0.11'],
            ['0.10.1', '0.10.2', '0.11.dev1324', '0.11'],
        ):
            org = list(versions)
            random.shuffle(versions)
            versions.sort(key=comparable_version)
            self.assertEqual(versions, org)

    def test_info_file(self):
        r_info = {
            "size": DUMMY_EGG_SIZE,
            "mtime": DUMMY_EGG_MTIME,
            "md5": DUMMY_EGG_MD5
        }

        info = info_file(DUMMY_EGG)
        self.assertEqual(info, r_info)

    def test_cleanup_url(self):
        r_data = [
            ("http://www.acme.com/", "http://www.acme.com/"),
            ("http://www.acme.com", "http://www.acme.com/"),
            ("file:///foo/bar", "file:///foo/bar/"),
        ]

        for url, r_url in r_data:
            self.assertEqual(cleanup_url(url), r_url)

    def test_cleanup_url_dir(self):
        if sys.platform == "win32":
            # The \\ -> / replace is a hack to deal with expanduser being
            # inconsistent on windows depending on whether HOME, USERPROFILE or
            # HOMEPATH is used
            home = os.path.expanduser("~").replace("\\", "/")
            p = "/" + os.path.abspath(home)
        else:
            p = os.path.abspath(os.path.expanduser("~"))
        r_url = "file://{0}/".format(p)

        url = "~"

        self.assertEqual(cleanup_url(url), r_url)

    def test_cleanup_url_relative_path(self):
        url, r_url = "file://foo/bar", "file://foo/bar/"

        self.assertEqual(cleanup_url(url), r_url)


class TestUri(unittest.TestCase):
    def test_path_to_uri_simple(self):
        """Ensure path to uri conversion works."""
        # XXX: this is a bit ugly, but urllib does not allow to select which OS
        # we want (there is no 'nturllib' or 'posixurllib' as there is for path.
        if sys.platform == "win32":
            r_uri = "file:///C:/Users/vagrant/yo"
            uri = path_to_uri("C:\\Users\\vagrant\\yo")
        else:
            r_uri = "file:///home/vagrant/yo"
            uri = path_to_uri("/home/vagrant/yo")
        self.assertEqual(r_uri, uri)

    def test_uri_to_path_simple(self):
        if sys.platform == "win32":
            r_path = "C:\\Users\\vagrant\\yo"
            uri = "file:///C:/Users/vagrant/yo"
        else:
            r_path = "/home/vagrant/yo"
            uri = "file:///home/vagrant/yo"

        path = uri_to_path(uri)
        self.assertEqual(r_path, path)

    def test_uri_to_path_simple_local(self):
        if sys.platform == "win32":
            r_path = "vagrant\\yo"
            uri = "file://vagrant/yo"
        else:
            r_path = "vagrant/yo"
            uri = "file://vagrant/yo"

        path = uri_to_path(uri)
        self.assertEqual(r_path, path)

    @contextlib.contextmanager
    def _patch_prefix(self, attr_name, prefix_value):
        # attr_name can be None to remove all venv prefixes
        prefix_names = ("real_prefix", "base_prefix")
        orig_attrs = {}
        for prefix_name in prefix_names:
            if hasattr(sys, prefix_name):
                orig_attrs[prefix_name] = getattr(sys, prefix_name)
                delattr(sys, prefix_name)

        try:
            if attr_name is not None:
                with mock.patch.object(sys, attr_name, prefix_value,
                                        create=True):
                    yield
            else:
                yield
        finally:
            for prefix_name, prefix_value in orig_attrs.items():
                setattr(sys, prefix_name, prefix_value)

    def _mock_under_non_venv(self):
        return self._patch_prefix(None, None)

    def _mock_under_venv(self):
        return self._patch_prefix("base_prefix",
                                  os.path.join(sys.prefix, 'venv'))

    def _mock_under_virtualenv(self):
        return self._patch_prefix("real_prefix",
                                  os.path.join(sys.prefix, 'venv'))

    def _mock_under_base_venv(self):
        return self._patch_prefix("base_prefix", sys.prefix)

    def _mock_under_virtualenv_under_base_venv(self):
        with self._patch_prefix("base_prefix", sys.prefix):
            return self._mock_under_virtualenv()

    def test_under_venv(self):
        def _check(mock_method, is_under_venv, prefix_name):
            with mock_method():
                self.assertEqual(under_venv(), is_under_venv)
                self.assertEqual(real_prefix(), getattr(sys, prefix_name))

        _check(self._mock_under_non_venv, False, "prefix")

        _check(self._mock_under_venv, True, "base_prefix")

        _check(self._mock_under_virtualenv, True, "real_prefix")

        _check(self._mock_under_base_venv, False, "prefix")

        _check(self._mock_under_virtualenv_under_base_venv,
               True, "real_prefix")


class TestPromptYesNo(unittest.TestCase):
    def test_simple(self):
        # Given
        message = "Do you want to do it ?"

        # When
        with mock_print() as m:
            with mock_raw_input("yes"):
                res = prompt_yes_no(message)

        # Then
        self.assertEqual(m.value.rstrip(), message)
        self.assertTrue(res)

    def test_simple_no(self):
        # Given
        message = "Do you want to do it ?"

        # When
        with mock_print() as m:
            with mock_raw_input("no"):
                res = prompt_yes_no(message)

        # Then
        self.assertEqual(m.value.rstrip(), message)
        self.assertFalse(res)

    def test_simple_force_yes(self):
        # Given
        message = "Do you want to do it ?"

        # When
        with mock_print() as m:
            with mock_raw_input("yes") as mocked_input:
                res = prompt_yes_no(message, True)

        # Then
        self.assertEqual(m.value.rstrip(), message)
        self.assertTrue(res)
        mocked_input.assert_not_called()


FAKE_USER = "john.doe"
FAKE_PASSWORD = "fake_password"


class TestInputAuth(unittest.TestCase):
    @mock.patch("enstaller.utils.getpass.getpass", lambda ignored: FAKE_PASSWORD)
    def test_simple(self):
        with mock_input(FAKE_USER):
            self.assertEqual(input_auth(), (FAKE_USER, FAKE_PASSWORD))

    @mock.patch("enstaller.utils.getpass.getpass", lambda ignored: FAKE_PASSWORD)
    def test_empty(self):
        with mock_input(""):
            self.assertEqual(input_auth(), (None, None))
