from __future__ import absolute_import

import contextlib
import json
import os.path
import re
import shutil
import sys
import tempfile
import textwrap

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from enstaller.vendor import responses

from enstaller.auth import UserPasswordAuth
from enstaller.main import main, main_noexc
from enstaller.config import (_set_keyring_password,
                              Configuration, write_default_config)

from enstaller.tests.common import (fake_keyring, mock_print, mock_input_auth,
                                    mock_raw_input)
from enstaller.vendor import requests
from enstaller.auth.tests.test_auth import R_JSON_AUTH_RESP

from .common import (
    empty_index, mock_install_req, use_given_config_context,
    without_any_configuration)

FAKE_USER = "nono"
FAKE_PASSWORD = "le petit robot"
FAKE_CREDS = UserPasswordAuth(FAKE_USER, FAKE_PASSWORD)._encoded_auth

class TestAuth(unittest.TestCase):
    @contextlib.contextmanager
    def assertSuccessfulExit(self):
        with self.assertRaises(SystemExit) as e:
            yield e
        self.assertEqual(e.exception.code, 0)

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.config = os.path.join(self.d, ".enstaller4rc")
        write_default_config(self.config)

    def tearDown(self):
        shutil.rmtree(self.d)

    def _run_main_with_dummy_req(self):
        with use_given_config_context(self.config):
            with self.assertSuccessfulExit():
                main_noexc(["dummy_requirement"])

    def _dummy_ssl_error_callback(self, request):
        msg = "Dummy SSL error"
        raise requests.exceptions.SSLError(msg, request=request)

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
        from enstaller.main import main
        with use_given_config_context(self.config):
            with mock_input_auth("", "") as m:
                with self.assertRaises(SystemExit):
                    main_noexc(["--userpass"])

        self.assertEqual(m.call_count, 3)

    @responses.activate
    def test_userpass_with_config(self):
        """
        Ensure enpkg --userpass doesn't crash when creds are invalid
        """
        responses.add(responses.GET,
                      "https://api.enthought.com/accounts/user/info/",
                      status=401,
                      content_type='application/json')
        r_output = textwrap.dedent("""\
        Could not authenticate as 'nono'
        Please check your credentials/configuration and try again
        (original error is: '401 Client Error: None').


        No modification was written.
        """)

        with use_given_config_context(self.config):
            with mock_print() as m:
                with mock_input_auth("nono", "robot"):
                    with self.assertRaises(SystemExit):
                        main_noexc(["--userpass"])

        self.assertMultiLineEqual(m.value, r_output)

    @mock_install_req
    @empty_index
    @responses.activate
    def test_enpkg_req_with_valid_auth(self):
        """
        Ensure 'enpkg req' authenticate as expected
        """
        with open(self.config, "w") as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        json_data = {
            "is_authenticated": True,
            "first_name": "nono",
            "last_name": "le petit robot",
            "has_subscription": True,
            "subscription_level": "free"
        }
        responses.add(responses.GET,
                      "https://api.enthought.com/accounts/user/info/",
                      body=json.dumps(json_data),
                      status=200,
                      content_type='application/json')

        with use_given_config_context(self.config):
            main(["nono"])

    @responses.activate
    def test_enpkg_req_with_invalid_auth(self):
        """
        Ensure 'enpkg req' doesn't crash when creds are invalid
        """
        self.maxDiff = None
        responses.add(responses.GET,
                      "https://api.enthought.com/accounts/user/info/",
                      status=401,
                      content_type='application/json')
        r_output = textwrap.dedent("""\
            Could not authenticate as 'nono'
            Please check your credentials/configuration and try again
            (original error is: '401 Client Error: None').


            You can change your authentication details with 'enpkg --userpass'.
        """)

        with open(self.config, "w") as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))

        with mock_print() as m:
            with use_given_config_context(self.config):
                with self.assertRaises(SystemExit):
                    main_noexc(["nono"])

        self.assertMultiLineEqual(m.value, r_output)

    @empty_index
    @mock_install_req
    @fake_keyring
    @responses.activate
    def test_no_keyring_to_no_keyring_conversion(self):
        """
        Ensure the config file is not converted when configured not to use
        keyring.
        """
        # Given
        with open(self.config, "w") as fp:
            fp.write("EPD_auth = '{0}'".format(FAKE_CREDS))
        config = Configuration.from_file(self.config)
        responses.add(responses.GET, config.api_url, status=200,
                      body=json.dumps(R_JSON_AUTH_RESP))

        # When
        self._run_main_with_dummy_req()

        # Then
        with open(self.config) as fp:
            self.assertMultiLineEqual(fp.read(), "EPD_auth = '{0}'".format(FAKE_CREDS))

    @empty_index
    @mock_install_req
    @fake_keyring
    @responses.activate
    def test_keyring_to_no_keyring_conversion(self):
        """
        Ensure the config file is automatically converted to use keyring.
        """
        # Given
        _set_keyring_password(FAKE_USER, FAKE_PASSWORD)
        with open(self.config, "w") as fp:
            fp.write("EPD_username = '{0}'".format(FAKE_USER))
        config = Configuration.from_file(self.config)
        responses.add(responses.GET, config.api_url, status=200,
                      body=json.dumps(R_JSON_AUTH_RESP))

        # When
        self._run_main_with_dummy_req()

        # Then
        with open(self.config) as fp:
            self.assertMultiLineEqual(fp.read(), "EPD_auth = '{0}'".format(FAKE_CREDS))


    @mock_install_req
    @fake_keyring
    @responses.activate
    def test_401_index_handling(self):
        self.maxDiff = None

        # Given
        repo = "http://acme.com/repo/ets/"
        config = Configuration()
        config.update(use_webservice=False, indexed_repositories=[repo])
        config.update(auth=("nono", "le petit robot"))
        config.write(self.config)

        url = repo + "index.json"
        responses.add(responses.HEAD, url, status=401)

        error_message = textwrap.dedent("""\
            Could not authenticate as 'nono'
            Please check your credentials/configuration and try again
            (original error is: '401 Client Error: None').


            You can change your authentication details with 'enpkg --userpass'.
        """)

        # When
        with use_given_config_context(self.config):
            with mock_print() as m:
                with self.assertRaises(SystemExit):
                    main(["dummy_requirement"])

        # Then
        self.assertMultiLineEqual(m.value, error_message)

    @mock_install_req
    @fake_keyring
    @responses.activate
    def test_invalid_certificate_use_webservice(self):
        self.maxDiff = None

        # Given
        url = "http://acme.com"
        config = Configuration()
        config.update(store_url=url)
        config.update(auth=("nono", "le petit robot"))
        config.write(self.config)

        def callback(request):
            msg = "Dummy SSL error"
            raise requests.exceptions.SSLError(msg, request)
        responses.add_callback(responses.GET, re.compile(url + "/*"),
                               callback)

        error_message = textwrap.dedent("""\
            SSL error: [Errno Dummy SSL error] <PreparedRequest [GET]>
            To connect to 'acme.com' insecurely, add the `-k` flag to enpkg command
        """)

        # When
        with use_given_config_context(self.config):
            with mock_print() as m:
                with self.assertRaises(SystemExit):
                    main(["dummy_requirement"])

        # Then
        self.assertMultiLineEqual(m.value, error_message)

    @mock_install_req
    @fake_keyring
    @responses.activate
    def test_invalid_certificate_dont_webservice(self):
        self.maxDiff = None

        # Given
        url = "http://acme.com"
        config = Configuration()
        config.update(use_webservice=False,
                      indexed_repositories=["http://acme.com/repo/"])
        config.update(auth=("nono", "le petit robot"))
        config.write(self.config)

        def callback(request):
            msg = "Dummy SSL error"
            raise requests.exceptions.SSLError(msg, request=request)
        responses.add_callback(responses.HEAD, re.compile(url + "/*"),
                               callback)

        error_message = textwrap.dedent("""\
            SSL error: Dummy SSL error
            To connect to 'acme.com' insecurely, add the `-k` flag to enpkg command
        """)

        # When
        with use_given_config_context(self.config):
            with mock_print() as m:
                with self.assertRaises(SystemExit):
                    main(["dummy_requirement"])

        # Then
        self.assertMultiLineEqual(m.value, error_message)

    @fake_keyring
    @responses.activate
    def test_invalid_certificate_config(self):
        self.maxDiff = None

        # Given
        url = "http://acme.com"
        config = Configuration()
        config.update(store_url=url)
        config.update(auth=("nono", "le petit robot"))
        config.write(self.config)

        responses.add_callback(responses.GET, re.compile(url + "/*"),
                               self._dummy_ssl_error_callback)

        error_message = "To connect to 'acme.com' insecurely, add the `-k` " \
                        "flag to enpkg command"

        # When
        with use_given_config_context(self.config):
            with mock_print() as m:
                with self.assertRaises(SystemExit):
                    main(["--config"])

        # Then
        last_line = m.value.splitlines()[-1]
        self.assertMultiLineEqual(last_line, error_message)
