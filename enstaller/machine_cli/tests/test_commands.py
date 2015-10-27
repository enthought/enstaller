import contextlib
import json
import mock
import shutil
import sys
import tempfile

from egginst._compat import PY2

from enstaller.auth import UserPasswordAuth
from enstaller.errors import EnstallerException
from enstaller.machine_cli.commands import (install, install_parse_json_string,
                                            remove, update_all,
                                            update_all_parse_json_string)
from enstaller.repository_info import BroodRepositoryInfo, FSRepositoryInfo
from enstaller.solver import Requirement
from enstaller.tests.common import mock_brood_repository_indices

if sys.version_info[0] == 2:
    import unittest2 as unittest
else:
    import unittest


@contextlib.contextmanager
def mock_stdin(bdata):
    if PY2:
        p = mock.patch("sys.stdin", spec=sys.stdin).__enter__()
        p.read.return_value = bdata
    else:
        p = mock.patch("sys.stdin", spec=sys.stdin).__enter__()
        p.buffer.read.return_value = bdata
    yield p


class TestParseJsonString(unittest.TestCase):
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

    def test_simple(self):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial",
                             "file://foo/bar"],
            "requirement": "numpy",
            "store_url": "https://acme.com",
        }
        r_repositories = (
            BroodRepositoryInfo("https://acme.com", "enthought/free"),
            BroodRepositoryInfo("https://acme.com", "enthought/commercial"),
            FSRepositoryInfo("file://foo/bar"),
        )

        # When
        config, requirement = install_parse_json_string(json.dumps(data))

        # Then
        self.assertEqual(config.auth, UserPasswordAuth("nono", "le petit robot"))
        self.assertEqual(config.repositories, r_repositories)
        self.assertIsNone(config.proxy)
        self.assertTrue(config.verify_ssl)
        self.assertEqual(requirement.name, "numpy")

    def test_proxy(self):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial",
                             "file://foo/bar"],
            "requirement": "numpy",
            "store_url": "https://acme.com",
        }

        # When
        config, requirement = install_parse_json_string(json.dumps(data))

        # Then
        self.assertIsNone(config.proxy)

        # Given
        data["proxy"] = "http://acme.com"

        # When
        config, requirement = install_parse_json_string(json.dumps(data))

        # Then
        self.assertEqual(config.proxy_dict, {"http": "http://acme.com:3128"})

    def test_verify_ssl(self):
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
        config, requirement = install_parse_json_string(json.dumps(data))

        # Then
        self.assertTrue(config.verify_ssl)

        # Given
        data["verify_ssl"] = False

        # When
        config, requirement = install_parse_json_string(json.dumps(data))

        # Then
        self.assertFalse(config.verify_ssl)

        # Given
        data["verify_ssl"] = True

        # When
        config, requirement = install_parse_json_string(json.dumps(data))

        # Then
        self.assertTrue(config.verify_ssl)


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    @mock_brood_repository_indices(
        {}, ["enthought/free", "enthought/commercial", "file://foo/bar"],
        store_url="https://acme.com"
    )
    @mock.patch("enstaller.machine_cli.commands.install_req")
    def test_simple(self, install_req):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial",
                             "file://foo/bar"],
            "requirement": "numpy",
            "store_url": "https://acme.com",
        }

        # When
        with mock_stdin(json.dumps(data).encode("utf8")):
            install()

        # Then
        self.assertTrue(install_req.called)
        self.assertEqual(
            install_req.call_args[0][2],
            Requirement.from_legacy_requirement_string("numpy")
        )


class TestRemove(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    @mock.patch("enstaller.machine_cli.commands.Enpkg.execute")
    @mock_brood_repository_indices(
        {}, ["enthought/free", "enthought/commercial", "file://foo/bar"],
        store_url="https://acme.com"
    )
    def test_simple(self, execute):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial",
                             "file://foo/bar"],
            "requirement": "numpy",
            "store_url": "https://acme.com",
        }
        r_operations = [("remove", "numpy-1.8.1-1.egg")]
        mocked_solver = mock.Mock()
        mocked_solver.resolve = mock.Mock(return_value=r_operations)

        # When
        with mock_stdin(json.dumps(data).encode("utf8")):
            with mock.patch(
                    "enstaller.machine_cli.commands.Enpkg._solver_factory",
                    return_value=mocked_solver):
                remove()

        # Then
        execute.assert_called_with(r_operations)

    @mock.patch("enstaller.machine_cli.commands.Enpkg.execute")
    @mock_brood_repository_indices(
        {}, ["enthought/commercial", "enthought/free", "file://foo/bar"],
        store_url="https://acme.com"
    )
    def test_simple_non_installed(self, execute):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial",
                             "file://foo/bar"],
            "requirement": "pandas",
            "store_url": "https://acme.com",
        }

        # When
        with mock_stdin(json.dumps(data).encode("utf8")):
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
    @mock_brood_repository_indices(
        {},
        ["enthought/commercial", "enthought/free", "file://foo/bar"],
        store_url="https://acme.com"
    )
    def test_simple(self, execute):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "files_cache": self.prefix,
            "repositories": ["enthought/free", "enthought/commercial",
                             "file://foo/bar"],
            "store_url": "https://acme.com",
        }

        # When
        with mock_stdin(json.dumps(data).encode("utf8")):
            update_all()
