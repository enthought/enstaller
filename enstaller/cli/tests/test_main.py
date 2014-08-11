import textwrap

from egginst._compat import TestCase

from enstaller.cli.commands import info_option
from enstaller.tests.common import (FAKE_MD5, FAKE_SIZE, PY_VER,
                                    create_repositories,
                                    dummy_repository_package_factory,
                                    mock_print)


class TestInfoStrings(TestCase):
    def test_info_option(self):
        self.maxDiff = None

        # Given
        r_output = textwrap.dedent("""\
        Package: enstaller

        Version: 4.6.2-1
            Product: commercial
            Available: True
            Python version: {2}
            Store location: {3}
            MD5: {0}
            Size: {1}
            Requirements: None
        Version: 4.6.3-1
            Product: commercial
            Available: True
            Python version: {2}
            Store location: {3}
            MD5: {0}
            Size: {1}
            Requirements: None
        """.format(FAKE_MD5, FAKE_SIZE, PY_VER, ""))

        entries = [dummy_repository_package_factory("enstaller", "4.6.2", 1),
                   dummy_repository_package_factory("enstaller", "4.6.3", 1)]

        remote_repository, installed_repository = \
                create_repositories(remote_entries=entries)

        # When
        with mock_print() as m:
            info_option(remote_repository, installed_repository,
                        "enstaller")
        # Then
        self.assertMultiLineEqual(m.value, r_output)
