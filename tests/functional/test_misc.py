import sys

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import mock

from enstaller.history import History
from enstaller.main import main_noexc

from enstaller.tests.common import mock_print

from .common import authenticated_config

class TestMisc(unittest.TestCase):
    @authenticated_config
    def test_list_bare(self):
        with mock.patch("enstaller.main.print_installed"):
            with self.assertRaises(SystemExit) as e:
                with mock_print() as m:
                    main_noexc(["--list"])
            self.assertMultiLineEqual(m.value, "prefix: {0}\n\n".format(sys.prefix))
            self.assertEqual(e.exception.code, 0)

    @authenticated_config
    def test_log(self):
        with mock.patch("enstaller.main.History", spec=History) as mocked_history:
            with self.assertRaises(SystemExit) as e:
                with mock_print() as m:
                    main_noexc(["--log"])
            self.assertEqual(e.exception.code, 0)
            self.assertTrue(mocked_history.return_value.print_log.called)
            self.assertMultiLineEqual(m.value, "")

    @authenticated_config
    def test_freeze(self):
        installed_requirements = ["dummy 1.0.0-1", "another_dummy 1.0.1-1"]
        with mock.patch("enstaller.main.get_freeze_list",
                        return_value=installed_requirements):
            with self.assertRaises(SystemExit) as e:
                with mock_print() as m:
                    main_noexc(["--freeze"])
            self.assertEqual(e.exception.code, 0)
            self.assertMultiLineEqual(m.value,
                                      "dummy 1.0.0-1\nanother_dummy 1.0.1-1\n")
