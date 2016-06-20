from __future__ import absolute_import, print_function

import datetime
import os
import shutil
import tempfile
import textwrap

import mock

from egginst._compat import assertCountEqual
from egginst.tests.common import mkdtemp
from egginst.vendor.six.moves import unittest

from enstaller.config import Configuration
from enstaller.tests.common import (FAKE_MD5, FAKE_SIZE, PY_VER,
                                    FakeOptions,
                                    create_prefix_with_eggs,
                                    create_repositories,
                                    dummy_installed_package_factory,
                                    dummy_repository_package_factory,
                                    mock_print)

from ..commands import (info_option, install_from_requirements, update_all,
                        whats_new)


class TestInfoStrings(unittest.TestCase):
    def test_info_option(self):
        self.maxDiff = None

        # Given
        mtime = 0.0
        r_output = textwrap.dedent("""\
        Package: enstaller

        Version: 4.6.2-1
            Product: commercial
            Available: True
            Python version: {2}
            Store location: {3}
            Last modified: {4}
            MD5: {0}
            Size: {1}
            Requirements: None
        Version: 4.6.3-1
            Product: commercial
            Available: True
            Python version: {2}
            Store location: {3}
            Last modified: {4}
            MD5: {0}
            Size: {1}
            Requirements: None
        """.format(FAKE_MD5, FAKE_SIZE, PY_VER, "",
                   datetime.datetime.fromtimestamp(mtime)))

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


class TestUpdatesCheck(unittest.TestCase):
    def test_whats_new_no_new_epd(self):
        # Given
        r_output = textwrap.dedent("""\
            Name                 installed            available
            ============================================================
            scipy                0.12.0-1             0.13.0-1
            numpy                1.7.1-1              1.7.1-2
            """)
        installed_entries = [
            dummy_installed_package_factory("numpy", "1.7.1", 1),
            dummy_installed_package_factory("scipy", "0.12.0", 1)
        ]
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.7.1", 2),
            dummy_repository_package_factory("scipy", "0.13.0", 1)
        ]

        remote, installed = create_repositories(remote_entries,
                                                installed_entries)

        # When
        with mock_print() as m:
            whats_new(remote, installed)

        # Then

        # FIXME: we splitlines and compared wo caring about order, as
        # the actual line order depends on dict ordering from
        # EggCollection.query_installed.
        assertCountEqual(self, m.value.splitlines(), r_output.splitlines())

    def test_whats_new_new_epd(self):
        # Given
        r_output = "EPD 7.3-2 is available. To update to it (with " \
                   "confirmation warning), run 'enpkg epd'.\n"
        installed_entries = [
            dummy_installed_package_factory("EPD", "7.2", 1),
        ]
        remote_entries = [
            dummy_repository_package_factory("EPD", "7.3", 2),
        ]

        remote, installed = create_repositories(remote_entries,
                                                installed_entries)

        # When
        with mock_print() as m:
            whats_new(remote, installed)

        # Then
        self.assertMultiLineEqual(m.value, r_output)

    def test_whats_new_no_updates(self):
        # Given
        r_output = "No new version of any installed package is available\n"

        installed_entries = [
            dummy_installed_package_factory("numpy", "1.7.1", 2),
            dummy_installed_package_factory("scipy", "0.13.0", 1)
        ]
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.7.1", 1),
            dummy_repository_package_factory("scipy", "0.12.0", 1)
        ]

        remote, installed = create_repositories(remote_entries,
                                                installed_entries)

        # When
        with mock_print() as m:
            whats_new(remote, installed)

        # Then
        self.assertMultiLineEqual(m.value, r_output)

    def test_update_all_no_updates(self):
        r_output = "No new version of any installed package is available\n"
        config = Configuration()

        installed_entries = [
            dummy_installed_package_factory("numpy", "1.7.1", 2),
            dummy_installed_package_factory("scipy", "0.13.0", 1)
        ]
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.7.1", 1),
            dummy_repository_package_factory("scipy", "0.12.0", 1)
        ]

        with mkdtemp() as d:
            enpkg = create_prefix_with_eggs(config, d,
                                            installed_entries, remote_entries)
            with mock_print() as m:
                update_all(enpkg, config, FakeOptions())
                self.assertMultiLineEqual(m.value, r_output)

    def test_update_all_no_epd_updates(self):
        r_output = textwrap.dedent("""\
        The following updates and their dependencies will be installed
        Name                 installed            available
        ============================================================
        scipy                0.13.0-1             0.13.2-1
        """)
        config = Configuration()

        installed_entries = [
            dummy_installed_package_factory("numpy", "1.7.1", 2),
            dummy_installed_package_factory("scipy", "0.13.0", 1),
            dummy_installed_package_factory("epd", "7.3", 1),
        ]
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.7.1", 1),
            dummy_repository_package_factory("scipy", "0.13.2", 1),
            dummy_repository_package_factory("epd", "7.3", 1),
        ]

        with mkdtemp() as d:
            enpkg = create_prefix_with_eggs(config, d, installed_entries, remote_entries)
            with mock.patch("enstaller.cli.commands.install_req") as mocked_install_req:
                with mock_print() as m:
                    update_all(enpkg, config, FakeOptions())
                    self.assertMultiLineEqual(m.value, r_output)
                    self.assertTrue(mocked_install_req.call_count >= 1)

    def test_update_all_epd_updates(self):
        r_output = textwrap.dedent("""\
        EPD 7.3-2 is available. To update to it (with confirmation warning), run 'enpkg epd'.
        The following updates and their dependencies will be installed
        Name                 installed            available
        ============================================================
        scipy                0.13.0-1             0.13.2-1
        """)
        config = Configuration()

        installed_entries = [
            dummy_installed_package_factory("numpy", "1.7.1", 2),
            dummy_installed_package_factory("scipy", "0.13.0", 1),
            dummy_installed_package_factory("epd", "7.3", 1),
        ]
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.7.1", 1),
            dummy_repository_package_factory("scipy", "0.13.2", 1),
            dummy_repository_package_factory("epd", "7.3", 2),
        ]

        with mkdtemp() as d:
            enpkg = create_prefix_with_eggs(config, d, installed_entries, remote_entries)
            with mock.patch("enstaller.cli.commands.install_req") as mocked_install_req:
                with mock_print() as m:
                    update_all(enpkg, config, FakeOptions())
                    self.assertMultiLineEqual(m.value, r_output)
                    self.assertTrue(mocked_install_req.call_count >= 1)


class TestInstallFromRequirements(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_install_from_requirements(self):
        # Given
        remote_entries = [
            dummy_repository_package_factory("numpy", "1.8.0", 1),
            dummy_repository_package_factory("numpy", "1.8.0", 2),
            dummy_repository_package_factory("nose", "1.2.1", 2),
            dummy_repository_package_factory("nose", "1.3.0", 1)
        ]

        requirements_file = os.path.join(self.prefix, "requirements.txt")
        with open(requirements_file, "w") as fp:
            fp.write("numpy 1.8.0-1\nnose 1.2.1-1")

        config = Configuration()
        enpkg = create_prefix_with_eggs(config, self.prefix, [], remote_entries)
        args = FakeOptions()
        args.requirements = requirements_file

        # When
        with mock.patch("enstaller.cli.commands.install_req") as mocked_install_req:
            install_from_requirements(enpkg, config, args)

        # Then
        mocked_install_req.assert_has_calls(
            [mock.call(enpkg, config, "numpy 1.8.0-1", args),
             mock.call(enpkg, config, "nose 1.2.1-1", args)])
