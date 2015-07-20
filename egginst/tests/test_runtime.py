import os.path
import sys

from egginst.vendor.okonomiyaki.platforms import EPDPlatform

from egginst.runtime import CPYTHON, RuntimeInfo


if sys.version_info[0] == 2:
    import unittest2 as unittest
else:
    import unittest


NORM_EXEC_PREFIX = os.path.normpath(sys.exec_prefix)
NORM_EXECUTABLE = os.path.normpath(sys.executable)


class TestRuntimeInfo(unittest.TestCase):
    def test_simple_from_running_python(self):
        # When
        runtime_info = RuntimeInfo.from_running_python()

        # Then
        self.assertEqual(runtime_info.prefix, NORM_EXEC_PREFIX)
        self.assertEqual(runtime_info.executable, NORM_EXECUTABLE)
        self.assertEqual(runtime_info.major, sys.version_info[0])
        self.assertEqual(runtime_info.minor, sys.version_info[1])
        self.assertEqual(runtime_info.implementation, CPYTHON)

    def test_from_prefix_and_platform(self):
        # Given
        prefix = "/usr/local"
        platform = EPDPlatform.from_epd_string("rh5-64").platform
        version_info = (3, 4, 3, "final", 0)

        # When
        runtime_info = RuntimeInfo.from_prefix_and_platform(
            prefix, platform, version_info)

        # Then
        self.assertEqual(runtime_info.executable, prefix + "/bin/python3")
        self.assertEqual(runtime_info.prefix, prefix)
        self.assertEqual(runtime_info.bindir, prefix + "/bin")
        self.assertEqual(runtime_info.scriptsdir, prefix + "/bin")
        self.assertEqual(
            runtime_info.site_packages, prefix + "/lib/python3.4/site-packages")
        self.assertEqual(runtime_info.major, 3)
        self.assertEqual(runtime_info.micro, 3)

        # Given
        prefix = "/usr/local"
        platform = EPDPlatform.from_epd_string("osx-64").platform
        version_info = (2, 7, 9, "final", 0)

        # When
        runtime_info = RuntimeInfo.from_prefix_and_platform(
            prefix, platform, version_info)

        # Then
        self.assertEqual(runtime_info.prefix, prefix)
        self.assertEqual(runtime_info.bindir, prefix + "/bin")
        self.assertEqual(runtime_info.scriptsdir, prefix + "/bin")
        self.assertEqual(
            runtime_info.site_packages, prefix + "/lib/python2.7/site-packages")
        self.assertEqual(runtime_info.major, 2)

        # Given
        prefix = "C:\\Python34"
        platform = EPDPlatform.from_epd_string("win-64").platform
        version_info = (3, 4, 3, "final", 0)

        # When
        runtime_info = RuntimeInfo.from_prefix_and_platform(
            prefix, platform, version_info)

        # Then
        self.assertEqual(runtime_info.prefix, prefix)
        self.assertEqual(runtime_info.bindir, prefix)
        self.assertEqual(runtime_info.scriptsdir, prefix + "\\Scripts")
        self.assertEqual(
            runtime_info.site_packages, prefix + "\\Lib\\site-packages")
        self.assertEqual(runtime_info.major, 3)

    def test_normalization(self):
        # Given
        prefix = "/usr/local/bin/.."
        norm_prefix = "/usr/local"
        platform = EPDPlatform.from_epd_string("osx-64").platform
        version_info = (2, 7, 9, "final", 0)

        # When
        runtime_info = RuntimeInfo.from_prefix_and_platform(
            prefix, platform, version_info)

        # Then
        self.assertEqual(runtime_info.prefix, norm_prefix)
        self.assertEqual(runtime_info.bindir, norm_prefix + "/bin")
        self.assertEqual(runtime_info.scriptsdir, norm_prefix + "/bin")
        self.assertEqual(
            runtime_info.site_packages, norm_prefix + "/lib/python2.7/site-packages")
        self.assertEqual(runtime_info.major, 2)
