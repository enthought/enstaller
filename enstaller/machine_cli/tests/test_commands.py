import json
import mock
import shutil
import tempfile

from egginst.vendor.six.moves import unittest

from enstaller.auth import UserPasswordAuth
from enstaller.errors import EnstallerException
from enstaller.machine_cli.commands import (install, install_parse_json_string,
                                            remove, update_all,
                                            update_all_parse_json_string)
from enstaller.solver import Requirement
from enstaller.tests.common import mock_index
from enstaller.utils import fill_url


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_invalid_parse_json_string(self):
        # Given
        data = {}

        # When/Then
        # Ensure we raise an EnstallerException for invalid json input data
        with self.assertRaises(EnstallerException):
            install_parse_json_string(json.dumps(data))

    def test_parse_json_string(self):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial"],
            "requirement": "numpy",
            "store_url": "https://acme.com",
        }
        r_repository_urls = (
            fill_url(
                "https://acme.com/repo/enthought/free/{PLATFORM}"),
            fill_url(
                "https://acme.com/repo/enthought/commercial/{PLATFORM}"),
        )

        # When
        config, requirement = install_parse_json_string(json.dumps(data))

        # Then
        self.assertEqual(config.auth, UserPasswordAuth("nono", "le petit robot"))
        self.assertEqual(config.indexed_repositories, r_repository_urls)
        self.assertEqual(requirement.name, "numpy")

    @mock_index({}, store_url="https://acme.com")
    @mock.patch("enstaller.machine_cli.commands.install_req")
    @mock.patch("sys.stdin")
    def test_simple(self, stdin, install_req):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial"],
            "requirement": "numpy",
            "store_url": "https://acme.com",
        }

        # When
        stdin.read.return_value = json.dumps(data).encode("utf8")
        install()

        # Then
        install_req.assert_called()
        install_req.call_args[0][2] == Requirement.from_anything("numpy")


class TestRemove(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    @mock.patch("enstaller.machine_cli.commands.Enpkg.execute")
    @mock.patch("sys.stdin")
    @mock_index({}, store_url="https://acme.com")
    def test_simple(self, stdin, execute):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial"],
            "requirement": "numpy",
            "store_url": "https://acme.com",
        }
        r_operations = [("remove", "numpy-1.8.1-1.egg")]
        mocked_solver = mock.Mock()
        mocked_solver.resolve = mock.Mock(return_value=r_operations)

        # When
        stdin.read.return_value = json.dumps(data).encode("utf8")
        with mock.patch(
                "enstaller.machine_cli.commands.Enpkg._solver_factory",
                return_value=mocked_solver):
            remove()

        # Then
        execute.assert_called_with(r_operations)

    @mock.patch("enstaller.machine_cli.commands.Enpkg.execute")
    @mock.patch("sys.stdin")
    @mock_index({}, store_url="https://acme.com")
    def test_simple_non_installed(self, stdin, execute):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial"],
            "requirement": "pandas",
            "store_url": "https://acme.com",
        }

        # When
        stdin.read.return_value = json.dumps(data).encode("utf8")
        remove()

        # Then
        execute.assert_not_called()


class TestUpdateAll(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_invalid_parse_json_string(self):
        # Given
        data = {}

        # When/Then
        # Ensure we raise an EnstallerException for invalid json input data
        with self.assertRaises(EnstallerException):
            update_all_parse_json_string(json.dumps(data))

    @mock.patch("enstaller.machine_cli.commands.Enpkg.execute")
    @mock.patch("sys.stdin")
    @mock_index({}, store_url="https://acme.com")
    def test_simple(self, stdin, execute):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial"],
            "store_url": "https://acme.com",
        }

        # When
        stdin.read.return_value = json.dumps(data).encode("utf8")
        update_all()
