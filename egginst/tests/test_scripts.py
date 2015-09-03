import hashlib
import os.path
import sys

import mock

from okonomiyaki.platforms import EPDPlatform
from zipfile2 import ZipFile

from egginst._compat import PY2, StringIO, configparser
from egginst import exe_data

from egginst.main import EggInst
from egginst.runtime import RuntimeInfo, _version_info_to_version
from egginst.scripts import (
    create_entry_points, create_proxies, fix_script, _get_executable
)
from egginst.utils import compute_md5

from .common import mkdtemp

if sys.version_info[0] == 2:
    import unittest2 as unittest
else:
    import unittest


DUMMY_EGG_WITH_PROXY = os.path.join(os.path.dirname(__file__), "data", "dummy_with_proxy-1.3.40-3.egg")
DUMMY_EGG_WITH_PROXY_SCRIPTS = os.path.join(os.path.dirname(__file__), "data", "dummy_with_proxy_scripts-1.0.0-1.egg")


class TestScripts(unittest.TestCase):
    def test_get_executable(self):
        executable = _get_executable()
        self.assertEqual(executable, sys.executable)

        executable = _get_executable(with_quotes=True)
        self.assertEqual(executable, "\"{0}\"".format(sys.executable))

        with mock.patch("egginst.scripts.on_win", "win32"):
            executable = _get_executable("python.exe")
            self.assertEqual(executable, "python.exe")

            executable = _get_executable("pythonw.exe")
            self.assertEqual(executable, "python.exe")

            executable = _get_executable("pythonw.exe", pythonw=True)
            self.assertEqual(executable, "pythonw.exe")


class TestFixScript(unittest.TestCase):
    def test_egginst_script_untouched(self):
        """
        Ensure we don't touch a script which has already been written by
        egginst.
        """
        simple_script = """\
#!/home/davidc/src/enthought/enstaller/.env/bin/python
# This script was created by egginst when installing:
#
#   enstaller-4.6.3.dev1-py2.7.egg
#
if __name__ == '__main__':
    import sys
    from enstaller.patch import main

    sys.exit(main())
"""

        with mkdtemp() as d:
            path = os.path.join(d, "script")
            with open(path, "wt") as fp:
                fp.write(simple_script)

            fix_script(path)

            with open(path, "rt") as fp:
                self.assertEqual(fp.read(), simple_script)

    def test_setuptools_script_fixed(self):
        """
        Ensure a script generated by setuptools is fixed.
        """
        setuptools_script = """\
#!/dummy_path/.env/bin/python
# EASY-INSTALL-ENTRY-SCRIPT: 'enstaller==4.6.3.dev1','console_scripts','enpkg'
__requires__ = 'enstaller==4.6.3.dev1'
import sys
from pkg_resources import load_entry_point

if __name__ == '__main__':
    sys.exit(
        load_entry_point('enstaller==4.6.3.dev1', 'console_scripts', 'enpkg')()
    )
"""
        if sys.platform == "win32":
            quoted_executable = '"' + sys.executable + '"'
        else:
            quoted_executable = sys.executable
        r_egginst_script = """\
#!{executable}
# EASY-INSTALL-ENTRY-SCRIPT: 'enstaller==4.6.3.dev1','console_scripts','enpkg'
__requires__ = 'enstaller==4.6.3.dev1'
import sys
from pkg_resources import load_entry_point

if __name__ == '__main__':
    sys.exit(
        load_entry_point('enstaller==4.6.3.dev1', 'console_scripts', 'enpkg')()
    )
""".format(executable=quoted_executable)

        with mkdtemp() as d:
            path = os.path.join(d, "script")
            with open(path, "wt") as fp:
                fp.write(setuptools_script)

            fix_script(path, sys.executable)

            with open(path, "rt") as fp:
                self.assertMultiLineEqual(fp.read(), r_egginst_script)


class TestCreateScript(unittest.TestCase):
    @mock.patch("egginst.utils.on_win", False)
    def test_simple(self):
        if sys.platform == "win32":
            q = "\""
        else:
            q = ""
        r_cli_entry_point = """\
#!{q}{executable}{q}
# This script was created by egginst when installing:
#
#   dummy.egg
#
if __name__ == '__main__':
    import sys
    from dummy import main_cli

    sys.exit(main_cli())
""".format(executable=sys.executable, q=q)

        entry_points = """\
[console_scripts]
dummy = dummy:main_cli

[gui_scripts]
dummy-gui = dummy:main_gui
"""
        s = StringIO(entry_points)
        config = configparser.ConfigParser()
        config.readfp(s)

        with mkdtemp() as d:
            egginst = EggInst("dummy.egg", d)
            create_entry_points(egginst, config)

            if sys.platform == "win32":
                entry_point = os.path.join(egginst.scriptsdir, "dummy-script.py")
            else:
                entry_point = os.path.join(egginst.scriptsdir, "dummy")
            self.assertTrue(os.path.exists(entry_point))

            with open(entry_point, "rt") as fp:
                cli_entry_point = fp.read()
                self.assertMultiLineEqual(cli_entry_point, r_cli_entry_point)

    @mock.patch("egginst.scripts.on_win", True)
    def test_simple_windows(self):
        python_executable = "C:\\Python27\\python.exe"
        pythonw_executable = "C:\\Python27\\pythonw.exe"

        r_cli_entry_point = """\
#!"{executable}"
# This script was created by egginst when installing:
#
#   dummy.egg
#
if __name__ == '__main__':
    import sys
    from dummy import main_cli

    sys.exit(main_cli())
""".format(executable=python_executable)

        r_gui_entry_point = """\
#!"{executable}"
# This script was created by egginst when installing:
#
#   dummy.egg
#
if __name__ == '__main__':
    import sys
    from dummy import main_gui

    sys.exit(main_gui())
""".format(executable=pythonw_executable)

        entry_points = """\
[console_scripts]
dummy = dummy:main_cli

[gui_scripts]
dummy-gui = dummy:main_gui
"""
        s = StringIO(entry_points)
        config = configparser.ConfigParser()
        config.readfp(s)

        with mkdtemp() as d:
            egginst = EggInst("dummy.egg", d)
            create_entry_points(egginst, config, python_executable)

            cli_entry_point_path = os.path.join(egginst.scriptsdir, "dummy-script.py")
            gui_entry_point_path = os.path.join(egginst.scriptsdir, "dummy-gui-script.pyw")
            entry_points = [
                os.path.join(egginst.scriptsdir, "dummy.exe"),
                os.path.join(egginst.scriptsdir, "dummy-gui.exe"),
                cli_entry_point_path, gui_entry_point_path,
            ]
            for entry_point in entry_points:
                self.assertTrue(os.path.exists(entry_point))

            with open(cli_entry_point_path, "rt") as fp:
                cli_entry_point = fp.read()
                self.assertMultiLineEqual(cli_entry_point, r_cli_entry_point)

            with open(gui_entry_point_path, "rt") as fp:
                gui_entry_point = fp.read()
                self.assertMultiLineEqual(gui_entry_point, r_gui_entry_point)

            self.assertEqual(compute_md5(os.path.join(egginst.scriptsdir, "dummy.exe")),
                             hashlib.md5(exe_data.cli).hexdigest())
            self.assertEqual(compute_md5(os.path.join(egginst.scriptsdir, "dummy-gui.exe")),
                             hashlib.md5(exe_data.gui).hexdigest())


class TestProxy(unittest.TestCase):
    def _runtime_info_factory(self, prefix):
        if sys.platform == "win32":
            epd_string = "win-32"
        else:
            epd_string = "rh5-32"
        # XXX: hack to force proper path separations, even on Unix.
        platform = EPDPlatform.from_epd_string(epd_string).platform
        runtime_info = RuntimeInfo.from_prefix_and_platform(
            prefix, platform, _version_info_to_version()
        )
        # Hack so that scriptsdir is a valid UNIX path (instead of
        # '/some/prefix\Scripts')
        runtime_info.scriptsdir = os.path.join(prefix, "Scripts")

        return runtime_info

    @mock.patch("egginst.utils.on_win", True)
    def test_proxy(self):
        """
        Test we handle correctly entries of the form 'path PROXY'.
        """
        r_python_proxy_data_template = """\
#!"%(executable)s"
# This proxy was created by egginst from an egg with special instructions
#
import sys
import subprocess

src = %(src)r

sys.exit(subprocess.call([src] + sys.argv[1:]))
"""

        with mkdtemp() as prefix:
            pythonexe = os.path.join(prefix, "python.exe")

            proxy_path = os.path.join(
                prefix, "EGG-INFO", "dummy_with_proxy", "usr", "swig.exe"
            )
            if PY2:
                proxy_path = proxy_path.decode("utf8")
            r_python_proxy_data = r_python_proxy_data_template % \
                {'executable': pythonexe, 'src': proxy_path}

            runtime_info = self._runtime_info_factory(prefix)
            egginst = EggInst(DUMMY_EGG_WITH_PROXY, runtime_info=runtime_info)

            with ZipFile(egginst.path) as zp:
                egginst.z = zp
                egginst.arcnames = zp.namelist()
                create_proxies(egginst, pythonexe)

                python_proxy = os.path.join(prefix, "Scripts", "swig-script.py")
                coff_proxy = os.path.join(prefix, "Scripts", "swig.exe")

                self.assertTrue(os.path.exists(python_proxy))
                self.assertTrue(os.path.exists(coff_proxy))

                self.assertTrue(compute_md5(coff_proxy),
                                hashlib.md5(exe_data.cli).hexdigest())

                with open(python_proxy, "rt") as fp:
                    python_proxy_data = fp.read()
                    self.assertMultiLineEqual(python_proxy_data,
                                              r_python_proxy_data)

    @mock.patch("egginst.utils.on_win", True)
    def test_proxy_directory(self):
        """
        Test we handle correctly entries of the form 'path some_directory'.
        """
        with mkdtemp() as prefix:
            with mock.patch("sys.executable", os.path.join(prefix, "python.exe")):
                runtime_info = self._runtime_info_factory(prefix)

                egginst = EggInst(
                    DUMMY_EGG_WITH_PROXY_SCRIPTS, runtime_info=runtime_info
                )
                with ZipFile(egginst.path) as zp:
                    egginst.z = zp
                    egginst.arcnames = zp.namelist()
                    create_proxies(egginst)

                    proxied_files = [
                        os.path.join(prefix, "Scripts", "dummy.dll"),
                        os.path.join(prefix, "Scripts", "dummy.lib"),
                    ]
                    for proxied_file in proxied_files:
                        self.assertTrue(os.path.exists(proxied_file))
