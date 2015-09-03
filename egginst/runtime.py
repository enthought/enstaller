import os.path
import ntpath
import posixpath
import subprocess
import sys

from egginst.vendor.okonomiyaki.platforms import Platform
from egginst.vendor.okonomiyaki.platforms.platform import WINDOWS
from egginst.vendor.okonomiyaki.versions import SemanticVersion


CPYTHON = "cpython"
PYPY = "pypy"

_DUMMY_NAME = "<enpkg>"


def _compute_site_packages(prefix, platform, major_minor):
    # Adapted from distutils.sysconfig.get_python_lib for 2.7.9
    prefix = prefix or sys.exec_prefix

    if platform.os == WINDOWS:
        return ntpath.join(prefix, "Lib", "site-packages")
    else:
        return posixpath.join(
            prefix, "lib", "python" + major_minor, "site-packages"
        )


def _version_info_to_version(version_info=None):
    version_info = version_info or sys.version_info
    version_string = ".".join(str(part) for part in version_info[:3])
    version_string += "-{0}.{1}".format(*version_info[-2:])
    return SemanticVersion.from_string(version_string)


class RuntimeInfo(object):
    """Information about an installed Runtime.
    """
    @classmethod
    def from_prefix_and_platform(cls, prefix, platform, version):
        """ Use this to compute runtime info for an arbitrary platform.

        Calling this with an incompatible platform (e.g. windows on linux) is
        undefined.

        Parameters
        ----------
        prefix: text
            An absolute path to the prefix (the root of the runtime), e.g. for
            a standard unix python, if python is in <prefix>/bin/python,
            <prefix> is the prefix.
        platform: Platform
            An okonomiyaki Platform class (the vendorized one).
        version: SemanticVersion
            The runtime's version
        """
        if platform.os == WINDOWS:
            scriptsdir = ntpath.join(prefix, "Scripts")
            paths = (prefix, scriptsdir)
        else:
            scriptsdir = bindir = posixpath.join(prefix, "bin")
            paths = (bindir, )

        if version.major == 3:
            executable = "python3"
        else:
            executable = "python"

        major_minor = "{0}.{1}".format(version.major, version.minor)

        if platform.os == WINDOWS:
            executable += ".exe"
            executable = ntpath.join(prefix, executable)
        else:
            executable = posixpath.join(scriptsdir, executable)

        site_packages = _compute_site_packages(prefix, platform, major_minor)

        return cls(
            "python", CPYTHON, version, platform, executable, paths,
            _DUMMY_NAME, prefix, scriptsdir, site_packages
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

        version = _version_info_to_version()

        major_minor = "{0}.{1}".format(version.major, version.minor)

        if platform.os == WINDOWS:
            scriptsdir = os.path.join(prefix, "Scripts")
            paths = (prefix, scriptsdir)
        else:
            scriptsdir = bindir = os.path.join(prefix, "bin")
            paths = (bindir,)

        site_packages = _compute_site_packages(prefix, platform, major_minor)

        return cls(
            "python", CPYTHON, version, platform, sys.executable, paths,
            _DUMMY_NAME, prefix, scriptsdir, site_packages
        )

    def __init__(self, language, implementation, version, platform, executable,
                 paths, name, prefix, scriptsdir, site_packages):
        def normpath(p):
            if platform.os == WINDOWS:
                return ntpath.normpath(p)
            else:
                return posixpath.normpath(p)

        # Language-agnostic attributes
        self.language = language
        self.implementation = implementation

        self.version = version
        "The runtime (full) version."

        self.platform = platform

        self._executable_value = normpath(executable)
        self._executable = None

        self.paths = tuple(normpath(p) for p in paths)
        "The paths that are part of the runtime."

        self.name = name

        self.prefix = normpath(prefix)
        "The runtime prefix."

        # Python-specific attributes
        self.scriptsdir = normpath(scriptsdir)
        "The directory where the scripts are installed."

        self.site_packages = normpath(site_packages)
        "The site packages directory."

    @property
    def executable(self):
        "The full path to the python binary."
        if self._executable is None:
            self._executable = self._compute_executable()
        return self._executable

    def py_call(self, cmd, *a, **kw):
        """ Call the given command with this runtime python (i.e. the actually
        executed command will be prefixed by this runtime's python executable).
        """
        assert issubclass(type(cmd), list)
        cmd = [self.executable] + cmd
        return subprocess.call(cmd, *a, **kw)

    def _compute_executable(self):
        if self.platform.os == WINDOWS:
            # Hack to take into account virtualenvs
            paths = (
                self._executable_value,
                ntpath.join(
                    self.scriptsdir, ntpath.basename(self._executable_value)
                )
            )
            for path in paths:
                if ntpath.isfile(path):
                    return path
            return self._executable_value
        else:
            return self._executable_value
