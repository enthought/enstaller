import os.path
import shutil
import sys
import tempfile

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from mock import patch

import enstaller.config

from enstaller.config import Configuration, write_default_config
from enstaller.errors import AuthFailedError, InvalidConfiguration
from enstaller.tests.common import fake_keyring


basic_user = dict(first_name="Jane", last_name="Doe", is_authenticated=True,
        has_subscription=True)
free_user = dict(first_name="John", last_name="Smith", is_authenticated=True,
        has_subscription=False)
anon_user = dict(is_authenticated=False)
old_auth_user = {}


@fake_keyring
class CheckedChangeAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, "enstaller4rc")

    def tearDown(self):
        shutil.rmtree(self.d)

    @patch('enstaller.config.authenticate', return_value=basic_user)
    def test_simple(self, mock1):
        config = Configuration()
        config.set_auth('usr', 'password')
        write_default_config(self.f)
        config._checked_change_auth(self.f)

        new_config = Configuration.from_file(self.f)
        usr = enstaller.config.authenticate(new_config)

        self.assertTrue(usr.get('is_authenticated'))
        self.assertTrue(usr.get('has_subscription'))

    def test_no_acct(self):
        def mocked_authenticate(configuration, remote=None):
            if configuration.get_auth() != ("valid_user", "valid_password"):
                raise AuthFailedError()
            else:
                return {"is_authenticated": True}

        write_default_config(self.f)
        with patch('enstaller.config.authenticate', mocked_authenticate):
            config = Configuration()
            config.set_auth("invalid_user", "invalid_password")

            with self.assertRaises(AuthFailedError):
                usr = config._checked_change_auth(self.f)

            config = Configuration()
            config.set_auth("valid_user", "valid_password")
            usr = config._checked_change_auth(self.f)

            self.assertEqual(usr, {"is_authenticated": True})

    @patch('enstaller.config.authenticate', return_value=old_auth_user)
    def test_remote_success(self, mock1):
        write_default_config(self.f)

        config = Configuration()
        config.set_auth("usr", "password")

        usr = config._checked_change_auth(self.f)
        self.assertEqual(usr, {})

    def test_nones(self):
        config = Configuration()

        with self.assertRaises(InvalidConfiguration):
            config.set_auth(None, None)

    def test_empty_strings(self):
        config = Configuration(use_keyring=False)
        config.set_auth("", "")

        with self.assertRaises(InvalidConfiguration):
            config._checked_change_auth(self.f)


class SearchTestCase(unittest.TestCase):
    pass


class InstallTestCase(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
