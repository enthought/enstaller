import json
import os.path
import platform
import shutil
import sys
import tempfile
import textwrap

import mock

from egginst.vendor.six.moves import unittest

from enstaller import __version__

from enstaller.config import _keyring_backend_name, Configuration
from enstaller.history import History
from enstaller.main import main_noexc
from enstaller.vendor import responses
from enstaller.utils import PY_VER

from enstaller.tests.common import mock_index, mock_print, R_JSON_AUTH_RESP

from .common import authenticated_config


class TestMisc(unittest.TestCase):
    @authenticated_config
    @responses.activate
    def test_print_config(self):
        self.maxDiff = None

        # Given
        config = Configuration()
        config.update(prefix=sys.prefix)

        template = textwrap.dedent("""\
Python version: {pyver}
enstaller version: {version}
sys.prefix: {sys_prefix}
platform: {platform}
architecture: {arch}
use_webservice: True
autoupdate: True
keyring backend: {keyring_backend}
settings:
    prefix = {prefix}
    repository_cache = {repository_cache}
    noapp = False
    proxy = None
You are logged in as 'dummy' (David Cournapeau).
Subscription level: Canopy / EPD Basic or above
""")
        r_output = template.format(pyver=PY_VER,
                                   sys_prefix=os.path.normpath(sys.prefix),
                                   version=__version__,
                                   platform=platform.platform(),
                                   arch=platform.architecture()[0],
                                   keyring_backend=_keyring_backend_name(),
                                   prefix=os.path.normpath(config.prefix),
                                   repository_cache=config.repository_cache)

        responses.add(responses.GET,
                      "https://api.enthought.com/accounts/user/info/",
                      body=json.dumps(R_JSON_AUTH_RESP))

        # When
        with self.assertRaises(SystemExit) as e:
            with mock_print() as m:
                main_noexc(["--config"])

        # Then
        self.assertEqual(e.exception.code, 0)
        self.assertMultiLineEqual(m.value, r_output)

    @authenticated_config
    def test_list_bare(self):
        # Given
        sys_prefix = os.path.normpath(sys.prefix)

        # When
        with mock.patch("enstaller.cli.commands.print_installed"):
            with self.assertRaises(SystemExit) as e:
                with mock_print() as m:
                    main_noexc(["--list"])

        # Then
        self.assertEqual(e.exception.code, 0)
        self.assertMultiLineEqual(m.value, "prefix: {0}\n\n".format(sys_prefix))

    @authenticated_config
    def test_log(self):
        with mock.patch("enstaller.cli.commands.History",
                        spec=History) as mocked_history:
            with self.assertRaises(SystemExit) as e:
                with mock_print() as m:
                    main_noexc(["--log"])
            self.assertEqual(e.exception.code, 0)
            self.assertTrue(mocked_history.return_value.print_log.called)
            self.assertMultiLineEqual(m.value, "")

    @authenticated_config
    def test_freeze(self):
        installed_requirements = ["dummy 1.0.0-1", "another_dummy 1.0.1-1"]
        with mock.patch("enstaller.cli.commands.get_freeze_list",
                        return_value=installed_requirements):
            with self.assertRaises(SystemExit) as e:
                with mock_print() as m:
                    main_noexc(["--freeze"])
            self.assertEqual(e.exception.code, 0)
            self.assertMultiLineEqual(m.value,
                                      "dummy 1.0.0-1\nanother_dummy 1.0.1-1\n")

    @mock_index({
        "fubar-1.0.0-1.egg": {
            "available": True,
            "build": 1,
            "md5": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "mtime": 0.0,
            "name": "fubar",
            "packages": [],
            "product": "nono",
            "python": PY_VER,
            "size": 0,
            "type": "egg",
            "version": "1.0.0"
            }}, "https://acme.com")
    def test_insecure_flag(self):
        # Given
        responses.add(responses.GET,
                      "https://acme.com/accounts/user/info/",
                      body=json.dumps(R_JSON_AUTH_RESP))

        config = Configuration()
        config.update(store_url="https://acme.com")
        config.update(auth=("nono", "le gros robot"))

        # When
        with self.assertRaises(SystemExit) as e:
            with mock.patch("enstaller.main._ensure_config_or_die",
                            return_value=config):
                with mock.patch("enstaller.main.convert_auth_if_required"):
                    main_noexc(["-s", "fubar"])

        # Then
        self.assertEqual(e.exception.code, 0)

        # When
        with self.assertRaises(SystemExit) as e:
            with mock.patch("enstaller.main._ensure_config_or_die",
                            return_value=config):
                with mock.patch("enstaller.main.convert_auth_if_required"):
                    main_noexc(["-ks", "fubar"])

        # Then
        self.assertEqual(e.exception.code, 0)


class TestPrefix(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    @authenticated_config
    @mock_index({
        "fubar-1.0.0-1.egg": {
            "available": True,
            "build": 1,
            "md5": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "mtime": 0.0,
            "name": "fubar",
            "packages": [],
            "product": "nono",
            "python": PY_VER,
            "size": 0,
            "type": "egg",
            "version": "1.0.0"
            }}, "https://api.enthought.com")
    def test_simple(self):
        self.maxDiff = None

        # Given
        responses.add(responses.GET,
                      "https://api.enthought.com/accounts/user/info/",
                      body=json.dumps(R_JSON_AUTH_RESP))

        template = textwrap.dedent("""\
Python version: {pyver}
enstaller version: {version}
sys.prefix: {sys_prefix}
platform: {platform}
architecture: {arch}
use_webservice: True
autoupdate: True
keyring backend: {keyring_backend}
settings:
    prefix = {prefix}
    repository_cache = {repository_cache}
    noapp = False
    proxy = None
You are logged in as 'dummy' (David Cournapeau).
Subscription level: Canopy / EPD Basic or above
""")
        r_output = template.format(pyver=PY_VER,
                                   sys_prefix=os.path.normpath(sys.prefix),
                                   version=__version__,
                                   platform=platform.platform(),
                                   arch=platform.architecture()[0],
                                   keyring_backend=_keyring_backend_name(),
                                   prefix=os.path.normpath(self.prefix),
                                   repository_cache=os.path.join(self.prefix,
                                                                 "LOCAL-REPO"))

        # When
        with self.assertRaises(SystemExit):
            with mock_print() as m:
                main_noexc(["--config", "--prefix={0}".format(self.prefix)])

        # Then
        self.assertEqual(m.value, r_output)
