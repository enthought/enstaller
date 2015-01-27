from __future__ import absolute_import

import os.path
import shutil
import sys
import tempfile
import textwrap

if sys.version_info < (2, 7):
    import unittest2 as unittest
    # FIXME: this looks quite fishy. On 2.6, with unittest2, the assertRaises
    # context manager does not contain the actual exception object ?
    def exception_code(ctx):
        return ctx.exception
else:
    import unittest
    def exception_code(ctx):
        return ctx.exception.code

import mock

from enstaller.main import main
from enstaller.tests.common import mock_print

from .common import (fake_empty_resolve, fake_configuration_and_auth,
                     enstaller_version, authenticated_config,
                     raw_input_always_yes, remote_enstaller_available)

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
            with mock.patch("enstaller.main.update_enstaller"):
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
            with mock.patch("enstaller.main.inplace_update"):
                main(["enstaller"])
        self.assertMultiLineEqual(m.value, r_output)

    @authenticated_config
    @raw_input_always_yes
    @enstaller_version("4.6.3")
    @remote_enstaller_available(["4.6.2"])
    @mock.patch("enstaller.main.logger")
    def test_updated_enstaller(self, logger):
        with mock.patch("enstaller.main.install_req"):
            main([""])
        logger.info.assert_called_with('prefix: %r',
                                       os.path.normpath(sys.prefix))

    @authenticated_config
    @raw_input_always_yes
    @enstaller_version("4.6.3")
    @remote_enstaller_available(["4.6.2"])
    def test_updated_enstaller_in_req(self):
        with mock_print() as m:
            with mock.patch("enstaller.main.install_req"):
                main(["enstaller"])
        self.assertMultiLineEqual(m.value, "")


class TestEnstallerInstallActions(unittest.TestCase):
    @fake_configuration_and_auth
    @fake_empty_resolve
    def test_install_numpy(self):
        main(["numpy"])

    @fake_configuration_and_auth
    @fake_empty_resolve
    def test_install_epd(self):
        with mock.patch("enstaller.main.epd_install_confirm") as m:
            main(["epd"])
        self.assertTrue(m.called)

    @fake_configuration_and_auth
    def test_remove_epd_fails(self):
        with mock.patch("enstaller.main.epd_install_confirm"):
            with mock.patch("enstaller.main.install_req"):
                with self.assertRaises(SystemExit) as e:
                    main(["--remove", "epd"])
                    self.assertNotEqual(exception_code(e), 0)

    @fake_configuration_and_auth
    def test_install_epd_and_other(self):
        with mock.patch("enstaller.main.epd_install_confirm"):
            with mock.patch("enstaller.main.install_req"):
                with self.assertRaises(SystemExit) as e:
                    main(["epd", "numpy"])
                self.assertNotEqual(exception_code(e), 0)

    @fake_configuration_and_auth
    def test_remove(self):
        with mock.patch("enstaller.main.Enpkg.execute"):
            main(["--remove", "numpy"])
