import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from enstaller.main import main_noexc

from .common import fake_configuration_and_auth


class TestRevert(unittest.TestCase):
    @fake_configuration_and_auth
    def test_simple(self):
        with mock.patch("enstaller.main.Enpkg.revert_actions"):
            with self.assertRaises(SystemExit) as e:
                main_noexc(["--revert", "10"])
            self.assertEqual(e.exception.code, 0)

    @fake_configuration_and_auth
    def test_no_actions(self):
        with mock.patch("enstaller.main.Enpkg") as enpkg:
            enpkg.return_value.configure_mock(**{"revert_actions.return_value": []})
            with self.assertRaises(SystemExit) as e:
                main_noexc(["--revert", "10"])
            self.assertEqual(e.exception.code, 0)
