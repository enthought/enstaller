import mock

from egginst.vendor.six.moves import unittest

from enstaller.machine_cli.__main__ import main
from enstaller.tests.common import exception_code


class TestMain(unittest.TestCase):
    def test_help(self):
        # given
        args = ["--help"]

        # when
        with self.assertRaises(SystemExit) as exc:
            main(args)

        # then
        self.assertEqual(exc.exception.code, 0)

    @mock.patch("enstaller.machine_cli.__main__.install")
    def test_install(self, install_command):
        # given
        args = ["install"]

        # when
        with self.assertRaises(SystemExit) as exc:
            main(args)

        # then
        self.assertEqual(exception_code(exc), 0)
        install_command.assert_called_with()

    @mock.patch("enstaller.machine_cli.__main__.remove")
    def test_remove(self, remove_command):
        # given
        args = ["remove"]

        # when
        with self.assertRaises(SystemExit) as exc:
            main(args)

        # then
        self.assertEqual(exception_code(exc), 0)
        remove_command.assert_called_with()

    @mock.patch("enstaller.machine_cli.__main__.update_all")
    def test_update_all(self, update_all_command):
        # given
        args = ["update_all"]

        # when
        with self.assertRaises(SystemExit) as exc:
            main(args)

        # then
        self.assertEqual(exception_code(exc), 0)
        update_all_command.assert_called_with()
