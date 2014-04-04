from __future__ import absolute_import

import sys
import textwrap

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from enstaller.errors import EXIT_ABORTED
from enstaller.main import main_noexc
from enstaller.tests.common import mock_print

from .common import set_env_vars, without_any_configuration

class TestEnstallerMainActions(unittest.TestCase):
    @without_any_configuration
    def test_print_version(self):
        # XXX: this is lousy test: we'd like to at least ensure we're printing
        # the correct version, but capturing the stdout is a bit tricky. Once
        # we replace print by proper logging, we should be able to do better.
        with self.assertRaises(SystemExit) as e:
            main_noexc(["--version"])
        self.assertEqual(e.exception.code, 0)

    @without_any_configuration
    def test_help_runs_and_exits_correctly(self):
        with self.assertRaises(SystemExit) as e:
            main_noexc(["--help"])
        self.assertEqual(e.exception.code, 0)

    @without_any_configuration
    def test_print_env(self):
        with self.assertRaises(SystemExit) as e:
            main_noexc(["--env"])
        self.assertEqual(e.exception.code, 0)

    @without_any_configuration
    def test_ctrl_c_handling(self):
        with mock.patch("enstaller.main.main", side_effect=KeyboardInterrupt):
            with self.assertRaises(SystemExit) as e:
                main_noexc()
            self.assertEqual(e.exception.code, EXIT_ABORTED)

    @without_any_configuration
    def test_crash_handling_default(self):
        r_output = textwrap.dedent("""\
        enstaller: Error: enstaller crashed (uncaught exception <type 'exceptions.Exception'>: Exception()).
        Please report this on enstaller issue tracker:
            http://github.com/enthought/enstaller/issues
        You can get a full traceback by setting the ENSTALLER_DEBUG environment variable
        """)
        with mock.patch("enstaller.main.main", side_effect=Exception):
            with mock_print() as mocked_print:
                with self.assertRaises(SystemExit) as e:
                    main_noexc()
                self.assertEqual(e.exception.code, 1)
            self.assertMultiLineEqual(mocked_print.value, r_output)

    @without_any_configuration
    def test_crash_handling_debug(self):
        with set_env_vars(ENSTALLER_DEBUG="1"):
            with mock.patch("enstaller.main.main", side_effect=Exception):
                with mock_print() as mocked_print:
                    with self.assertRaises(Exception):
                        main_noexc()
                self.assertMultiLineEqual(mocked_print.value, "")
