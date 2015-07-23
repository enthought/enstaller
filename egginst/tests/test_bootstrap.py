import shutil
import sys
import tempfile

import mock
import testfixtures

from egginst.bootstrap import main

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest


class TestEgginstBootstrap(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    @mock.patch("egginst.main.install_egg_cli")
    def test_main(self, install_egg_cli):
        # Given
        r_egg = "enstaller-4.8.0-1.egg"
        r_output = 'Bootstrapping: {0}'.format(r_egg)

        # When
        with mock.patch("sys.argv", [r_egg]):
            with testfixtures.OutputCapture() as output:
                main(prefix=self.prefix, verbose=False)

        # Then
        self.assertEqual(install_egg_cli.called, 1)
        call_args = install_egg_cli.call_args[0]
        egg, _, noapp = call_args
        self.assertEqual(egg, r_egg)
        self.assertIs(noapp, False)

        output.compare(r_output)
