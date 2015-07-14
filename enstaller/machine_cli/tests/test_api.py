import json
import os.path
import sys

import mock

from enstaller import Configuration

from egginst._compat import binary_type
from enstaller.auth import UserPasswordAuth
from enstaller.errors import ProcessCommunicationError

from ..api import SubprocessEnpkgExecutor

if sys.version_info[0] == 2:
    import unittest2 as unittest
else:
    import unittest


def mock__run_command(f):
    path = "enstaller.machine_cli.api.SubprocessEnpkgExecutor._run_command"
    return mock.patch(path)(f)


class TestAPI(unittest.TestCase):
    def setUp(self):
        # Given
        self.python_path = os.path.join("fubar", "bin", "python")
        self.store_url = "https://acme.com"
        self.simple_auth = UserPasswordAuth("nono@fake.domain", "yeye")
        self.repositories = ["enthought/free", "enthought/commercial",
                             "file://foo/bar"]
        self.repository_cache = os.path.abspath(os.path.join("unused",
                                                             "directory"))

    @mock__run_command
    def test_install(self, run_command):
        # Given
        r_json_data = {
            "authentication": {
                "kind": "simple",
                "username": self.simple_auth.username,
                "password": self.simple_auth.password,
            },
            'files_cache': self.repository_cache,
            'repositories': self.repositories,
            'requirement': 'numpy',
            'store_url': self.store_url,
            'verify_ssl': True,
        }

        # When
        executor = SubprocessEnpkgExecutor(self.python_path, self.store_url,
                                           self.simple_auth, self.repositories,
                                           self.repository_cache)
        executor.install("numpy")

        # Then
        self.assertEqual(run_command.called, 1)
        args = run_command.call_args[0]
        self.assertEqual(args[0], "install")
        self.assertEqual(args[1], r_json_data)

    @mock__run_command
    def test_remove(self, run_command):
        # Given
        python_path = os.path.join("fubar", "bin", "python")

        r_json_data = {
            "authentication": {
                "kind": "simple",
                "username": self.simple_auth.username,
                "password": self.simple_auth.password,
            },
            'files_cache': self.repository_cache,
            'repositories': self.repositories,
            'requirement': 'numpy',
            'store_url': self.store_url,
            'verify_ssl': True,
        }

        # When
        executor = SubprocessEnpkgExecutor(python_path, self.store_url,
                                           self.simple_auth, self.repositories,
                                           self.repository_cache)
        executor.remove("numpy")

        # Then
        self.assertEqual(run_command.called, 1)
        args = run_command.call_args[0]
        self.assertEqual(args[0], "remove")
        self.assertEqual(args[1], r_json_data)

    @mock__run_command
    def test_update_all(self, run_command):
        # Given
        python_path = os.path.join("fubar", "bin", "python")

        r_json_data = {
            "authentication": {
                "kind": "simple",
                "username": self.simple_auth.username,
                "password": self.simple_auth.password,
            },
            'files_cache': self.repository_cache,
            'repositories': self.repositories,
            'store_url': self.store_url,
            'verify_ssl': True,
        }

        # When
        executor = SubprocessEnpkgExecutor(python_path, self.store_url,
                                           self.simple_auth, self.repositories,
                                           self.repository_cache)
        executor.update_all()

        # Then
        self.assertEqual(run_command.called, 1)
        args = run_command.call_args[0]
        self.assertEqual(args[0], "update_all")
        self.assertEqual(args[1], r_json_data)

    def test__run_command_simple(self):
        # Given
        r_json_data = {
            "authentication": {
                "kind": "simple",
                "username": self.simple_auth.username,
                "password": self.simple_auth.password,
            },
            'files_cache': self.repository_cache,
            'repositories': self.repositories,
            'requirement': 'numpy',
            'store_url': self.store_url,
            'verify_ssl': True,
        }
        r_cmd = [sys.executable, "-m", "enstaller.machine_cli.__main__", "install"]

        # When
        executor = SubprocessEnpkgExecutor(sys.executable, self.store_url,
                                           self.simple_auth, self.repositories,
                                           self.repository_cache)

        with mock.patch("enstaller.machine_cli.api.subprocess") as p:
            p.Popen.return_value.communicate.return_value = [b"", b""]
            p.Popen.return_value.returncode = 0
            executor.install("numpy")

        # Then
        p.Popen.assert_called_with(r_cmd, stdin=p.PIPE)

        # We cannot test assert_called_with as the json string depends on dict
        # order. Instead, we decode the passed argument to check we have the
        # right data
        self.assertEqual(p.Popen.return_value.communicate.called, 1)
        args = p.Popen.return_value.communicate.call_args[0]
        self.assertIsInstance(args[0], binary_type)
        self.assertEqual(json.loads(args[0].decode("utf8")), r_json_data)

    def test__run_command_invalid_python_path(self):
        # When/Then
        executor = SubprocessEnpkgExecutor(self.python_path, self.store_url,
                                           self.simple_auth, self.repositories,
                                           self.repository_cache)

        with mock.patch("enstaller.machine_cli.api.subprocess"):
            with self.assertRaises(ValueError):
                executor.install("numpy")

    def test__run_command_failing_subprocess(self):
        # When/Then
        executor = SubprocessEnpkgExecutor(sys.executable, self.store_url,
                                           self.simple_auth, self.repositories,
                                           self.repository_cache)

        with mock.patch("enstaller.machine_cli.api.subprocess") as p:
            p.Popen.return_value.communicate.return_value = [b"", b""]
            p.Popen.return_value.returncode = 1

            with self.assertRaises(ProcessCommunicationError):
                executor.install("numpy")

    @mock__run_command
    def test_from_configuration(self, run_command):
        # Given
        r_json_data = {
            "authentication": {
                "kind": "simple",
                "username": self.simple_auth.username,
                "password": self.simple_auth.password,
            },
            'files_cache': self.repository_cache,
            'repositories': self.repositories,
            'requirement': 'numpy',
            'store_url': self.store_url,
            'verify_ssl': True,
        }
        config = Configuration(store_url=self.store_url,
                               auth=self.simple_auth,
                               repository_cache=self.repository_cache,
                               use_webservice=False)
        config.set_repositories_from_names(self.repositories)

        # When
        executor = SubprocessEnpkgExecutor.from_configuration(self.python_path,
                                                              config)
        executor.install("numpy")

        # Then
        self.assertEqual(run_command.called, 1)
        args = run_command.call_args[0]
        self.assertEqual(args[0], "install")
        self.assertEqual(args[1], r_json_data)
