from __future__ import absolute_import

import contextlib
import os.path
import shutil
import sys
import tempfile
import textwrap

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from enstaller.main import main_noexc
from enstaller.config import _encode_auth, _set_keyring_password

from enstaller.tests.common import (
    fake_keyring, mock_print, fail_authenticate, mock_input_auth,
    succeed_authenticate)

from .common import (
    empty_index, mock_install_req, use_given_config_context,
    without_any_configuration)

FAKE_USER = "nono"
FAKE_PASSWORD = "le petit robot"
FAKE_CREDS = _encode_auth(FAKE_USER, FAKE_PASSWORD)

class TestAuth(unittest.TestCase):
    @contextlib.contextmanager
    def assertSuccessfulExit(self):
        with self.assertRaises(SystemExit) as e:
            yield e
        self.assertEqual(e.exception.code, 0)

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.config = os.path.join(self.d, ".enstaller4rc")

    def tearDown(self):
        shutil.rmtree(self.d)

    def _run_main_with_dummy_req(self):
        with use_given_config_context(self.config):
            with self.assertSuccessfulExit():
                main_noexc(["dummy_requirement"])

    def test_auth_requested_without_config(self):
        """
        Ensure we ask for authentication if no .enstaller4rc is found.
        """
        with use_given_config_context(self.config):
            with mock_print() as m:
                with mock.patch("enstaller.main.configure_authentication_or_exit",
                                lambda *a: sys.exit(-1)):
                    with self.assertRaises(SystemExit):
                        main_noexc([])

        self.assertMultiLineEqual(m.value, "")

    @without_any_configuration
    def test_userpass_without_config(self):
        """
        Ensure we don't crash when empty information is input in --userpass
        prompt (no .enstaller4rc found).
        """
        with use_given_config_context(self.config):
            with mock.patch("__builtin__.raw_input", return_value="") as m:
                with self.assertRaises(SystemExit):
                    main_noexc(["--userpass"])

        self.assertEqual(m.call_count, 3)

    @fail_authenticate
    def test_userpass_with_config(self):
        """
        Ensure enpkg --userpass doesn't crash when creds are invalid
        """
        r_output = textwrap.dedent("""\
        Could not authenticate with user 'nono' against 'https://api.enthought.com'. Please check
        your credentials/configuration and try again (original error is:
        'Dummy auth error').


        No modification was written.
        """)

        with use_given_config_context(self.config):
            with mock_print() as m:
                with mock_input_auth("nono", "robot"):
                    with self.assertRaises(SystemExit):
                        main_noexc(["--userpass"])

        self.assertMultiLineEqual(m.value, r_output)

    @fail_authenticate
    def test_enpkg_req_with_invalid_auth(self):
        """
        Ensure 'enpkg req' doesn't crash when creds are invalid
        """
        self.maxDiff = None
        r_output = textwrap.dedent("""\
            Could not authenticate with user 'nono' against 'https://api.enthought.com'. Please check
            your credentials/configuration and try again (original error is:
            'Dummy auth error').


            You can change your authentication details with 'enpkg --userpass'.
        """)

        with open(self.config, "w") as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        with mock_print() as m:
            with use_given_config_context(self.config):
                with self.assertRaises(SystemExit):
                    main_noexc(["nono"])

        self.assertMultiLineEqual(m.value, r_output)

    @succeed_authenticate
    @empty_index
    @mock_install_req
    @fake_keyring
    def test_no_keyring_to_no_keyring_conversion(self):
        """
        Ensure the config file is not converted when configured not to use
        keyring.
        """
        # Given
        with open(self.config, "w") as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        # When
        self._run_main_with_dummy_req()

        # Then
        with open(self.config) as fp:
            self.assertMultiLineEqual(fp.read(), "EPD_auth = '{0}'".format(FAKE_CREDS))

    @empty_index
    @succeed_authenticate
    @mock_install_req
    @fake_keyring
    def test_keyring_to_no_keyring_conversion(self):
        """
        Ensure the config file is automatically converted to use keyring.
        """
        # Given
        _set_keyring_password(FAKE_USER, FAKE_PASSWORD)
        with open(self.config, "w") as fp:
            fp.write("EPD_username = '{0}'".format(FAKE_USER))

        # When
        self._run_main_with_dummy_req()

        # Then
        with open(self.config) as fp:
            self.assertMultiLineEqual(fp.read(), "EPD_auth = '{0}'".format(FAKE_CREDS))
