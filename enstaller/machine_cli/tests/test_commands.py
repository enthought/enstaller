import json
import mock

from egginst.vendor.six.moves import unittest

from enstaller.auth import UserPasswordAuth
from enstaller.machine_cli.commands import install, install_parse_json_string, main
from enstaller.tests.common import exception_code, mock_index


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
            "requirement": "numpy",
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            }
        }

        # When
        config, requirement = install_parse_json_string(json.dumps(data))

        # Then
        self.assertEqual(config.auth, UserPasswordAuth("nono", "le petit robot"))
        self.assertEqual(requirement.name, "numpy")

    @mock_index({})
    @mock.patch("enstaller.machine_cli.commands.install_req")
    def test_simple(self, install_req):
        # Given
        data = {
            "requirement": "numpy",
            "authentication": {
                "kind": "simple",
                "username": "nono",
                "password": "le petit robot",
            }
        }

        # When
        install(json.dumps(data))

        # Then
        install_req.assert_called()
