import json
import mock

from egginst.vendor.six.moves import unittest

from enstaller.auth import UserPasswordAuth
from enstaller.machine_cli.commands import install, install_parse_json_string, main
from enstaller.tests.common import exception_code, mock_index
from enstaller.utils import fill_url


class TestMain(unittest.TestCase):
    def test_help(self):
        # given
        args = ["--help"]

        # when
        with self.assertRaises(SystemExit) as exc:
            main(args)

        # then
        self.assertEqual(exception_code(exc), 0)

    @mock.patch("enstaller.machine_cli.commands.install")
    def test_install(self, install_command):
        # given
        args = ["install", "{}"]

        # when
        with self.assertRaises(SystemExit) as exc:
            main(args)

        # then
        self.assertEqual(exception_code(exc), 0)
        install_command.assert_called_with("{}")


class TestInstall(unittest.TestCase):
    def test_parse_json_string(self):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
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
    def test_simple(self, install_req):
        # Given
        data = {
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            },
            "repositories": ["enthought/free", "enthought/commercial"],
            "requirement": "numpy",
            "store_url": "https://acme.com",
        }

        # When
        install(json.dumps(data))

        # Then
        install_req.assert_called()
