from __future__ import absolute_import

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

from enstaller.config import Configuration
from enstaller.main import main
from enstaller.tests.common import (
    fake_keyring, mock_print, fail_authenticate, mock_input_auth,
    succeed_authenticate)

from .common import (use_given_config_context, without_any_configuration,
    enstaller_version, authenticated_config, raw_input_always_yes,
    remote_enstaller_available)

class TestEnstallerMainActions(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.config = os.path.join(self.d, ".enstaller4rc")

    def tearDown(self):
        shutil.rmtree(self.d)

    @authenticated_config
    @raw_input_always_yes
    @enstaller_version("4.6.1")
    @remote_enstaller_available(["4.6.2"])
    def test_automatic_update(self):
        r_output = textwrap.dedent("""\
            Enstaller has been updated.
            Please re-run your previous command.
        """)

        with mock_print() as m:
            with mock.patch("enstaller.main.install_req"):
                main([""])
        self.assertMultiLineEqual(m.value, r_output)

    @authenticated_config
    @raw_input_always_yes
    @enstaller_version("4.6.1")
    @remote_enstaller_available(["4.6.2"])
    def test_enstaller_in_req(self):
        r_output = textwrap.dedent("""\
            Enstaller has been updated.
            Please re-run your previous command.
        """)

        with mock_print() as m:
            with mock.patch("enstaller.main.install_req"):
                main(["enstaller"])
        self.assertMultiLineEqual(m.value, r_output)

    @authenticated_config
    @raw_input_always_yes
    @enstaller_version("4.6.3")
    @remote_enstaller_available(["4.6.2"])
    def test_updated_enstaller(self):
        r_output = textwrap.dedent("""\
            Enstaller is already up to date, not upgrading.
            prefix: {0}
        """.format(sys.prefix))

        with mock_print() as m:
            with mock.patch("enstaller.main.install_req"):
                main([""])
        self.assertMultiLineEqual(m.value, r_output)

    @authenticated_config
    @raw_input_always_yes
    @enstaller_version("4.6.3")
    @remote_enstaller_available(["4.6.2"])
    def test_updated_enstaller_in_req(self):
        r_output = textwrap.dedent("""\
            Enstaller is already up to date, not upgrading.
            prefix: {0}
        """.format(sys.prefix))

        with mock_print() as m:
            with mock.patch("enstaller.main.install_req"):
                main(["enstaller"])
        self.assertMultiLineEqual(m.value, r_output)
