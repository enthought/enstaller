import os.path
import ntpath
import posixpath
import site
import subprocess
import sys

from egginst.vendor.okonomiyaki.platforms import Platform
from egginst.vendor.okonomiyaki.platforms.platform import WINDOWS


CPYTHON = "cpython"
PYPY = "pypy"


def _compute_site_packages(prefix, platform, major_minor):
    # Adapted from distutils.sysconfig.get_python_lib for 2.7.9
    prefix = prefix or sys.exec_prefix

    if platform.os == WINDOWS:
        return ntpath.join(prefix, "Lib", "site-packages")
    else:
        return posixpath.join(
            prefix, "lib", "python" + major_minor, "site-packages"
        )


class RuntimeInfo(object):
    @classmethod
    def from_prefix_and_platform(cls, prefix, platform, version_info):
        """ Use this to compute runtime info for an arbitrary platform.

        Calling this with an incompatible platform (e.g. windows on linux) is
        undefined.

        Parameters
        ----------
        platform: Platform
            An okonomiyaki Platform class (the vendorized one).
        """
        if platform.os == WINDOWS:
            bindir = prefix
            scriptsdir = ntpath.join(prefix, "Scripts")
        else:
            bindir = scriptsdir = posixpath.join(prefix, "bin")

        if version_info[0] == 3:
            executable = "python3"
        else:
            executable = "python"

        if platform.os == WINDOWS:
            executable += ".exe"
            executable = ntpath.join(bindir, executable)
        else:
            executable = posixpath.join(bindir, executable)

        major_minor = "{0}.{1}".format(*version_info[:2])
        site_packages = _compute_site_packages(prefix, platform, major_minor)

        return cls(
            prefix, bindir, scriptsdir, site_packages, executable,
            version_info, platform, CPYTHON,
        )

    @classmethod
    def from_running_python(cls, platform=None):
        """ Use this to compute runtime info from the running python.

        Calling this with an incompatible platform (e.g. windows on linux) is
        undefined.

        Parameters
        ----------
        platform: Platform
            An okonomiyaki Platform class (the vendorized one).
        """
        prefix = sys.exec_prefix

        platform = platform or Platform.from_running_python()

        if platform.os == WINDOWS:
            bindir = prefix
            scriptsdir = os.path.join(prefix, "Scripts")
        else:
            bindir = scriptsdir = os.path.join(prefix, "bin")

        getsitepackages = getattr(site, "getsitepackages", None)
        if getsitepackages is not None:
            site_packages = getsitepackages()
        else:
            major_minor = "{0}.{1}".format(*sys.version_info[:2])
            site_packages = _compute_site_packages(
                prefix, platform, major_minor
            )

        return cls(
            prefix, bindir, scriptsdir, site_packages, sys.executable,
            sys.version_info, platform, CPYTHON,
        )

    def __init__(self, prefix, bindir, scriptsdir, site_packages, executable,
                 version_info, platform, implementation):
        self.prefix = os.path.normpath(prefix)
        self.bindir = os.path.normpath(bindir)
        self.scriptsdir = os.path.normpath(scriptsdir)
        self.site_packages = os.path.normpath(site_packages)
        self.executable = os.path.normpath(executable)

        self.version_info = version_info

        self.platform = platform
        self.implementation = implementation

    @property
    def major(self):
        return self.version_info[0]

    @property
    def minor(self):
        return self.version_info[1]

    @property
    def micro(self):
        return self.version_info[2]

    def py_call(self, cmd, *a, **kw):
        """ Call the given command with this runtime python (i.e. the actually
        executed command will be prefixed by this runtime's python executable).
        """
        assert issubclass(type(cmd), list)
        cmd = [self._actual_executable] + cmd
        return subprocess.call(cmd, *a, **kw)

    @property
    def _actual_executable(self):
        if self.platform.os == WINDOWS:
            # Hack to take into account virtualenvs
            paths = (
                self.executable,
                ntpath.join(self.scriptsdir, ntpath.basename(self.executable))
            )
            for path in paths:
                if ntpath.isfile(path):
                    return path
            return self.executable
        else:
            return self.executable
