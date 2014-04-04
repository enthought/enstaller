from __future__ import absolute_import

import sys

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from enstaller.main import main_noexc

from .common import without_any_configuration

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
