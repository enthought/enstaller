from __future__ import print_function

import logging
import os
import sys
import textwrap
import re
from os.path import abspath, basename, join, isfile, islink

from egginst.exe_data import cli, gui
from egginst.utils import makedirs, on_win, rm_rf

hashbang_pat = re.compile(r'#!.+$', re.M)
logger = logging.getLogger(__name__)


def create_entry_point(entry_point, bindir, template=None,
                       pythonexe=sys.executable):
    """ Writes the various files needed for the given entry point.

    Parameters
    ----------
    entry_point: _EntryPoint
        Entry point metadata
    bindir: str
        The install prefix where to install the entry point file(s)
    template: str
        A template for the python entry point script. May be useful if you need
        to tweak the entry point.
    pythonexe: str
        The python executable to use in the entry point.
    """
    template = template or _DEFAULT_TEMPLATE

    created_files = []

    fname = entry_point.name

    if on_win:
        exe_path = join(bindir, '%s.exe' % entry_point.name)
        _write_exe(exe_path, entry_point.kind)
        fname += '-script.py'
        if isinstance(entry_point, GUIScript):
            fname += 'w'
        created_files.append(exe_path)

    path = join(bindir, fname)
    _write_script(path, entry_point, template, pythonexe)

    created_files.append(path)

    return created_files


def create_entry_points(egg, conf, pythonexe=sys.executable):
    """ Create the entry points from the given Configuration instance.
    """
    template = textwrap.dedent("""\
    #!{python}
    # This script was created by egginst when installing:
    #
    #   %(egg_name)s
    #
    if __name__ == '__main__':
        import sys
        from {module} import {func}

        sys.exit({func}())
    """ % {"egg_name": egg.fn})

    makedirs(egg.scriptsdir)

    for script_type in ['gui_scripts', 'console_scripts']:
        if script_type not in conf.sections():
            continue
        for name, value in conf.items(script_type):
            if script_type == "gui_scripts":
                entry_point = GUIScript.from_string(name, value)
            elif script_type == "console_scripts":
                entry_point = ConsoleScript.from_string(name, value)
            created_files = create_entry_point(
                entry_point, egg.scriptsdir, template, pythonexe
            )
            egg.files.extend(created_files)


def create_proxies(egg, pythonexe=sys.executable):
    """ Create so-called 'proxy' files on windows.

    Proxies are essentially entry points, which redirect to actual executables
    in locations not in %PATH%.
    """
    # This function is called on Windows only
    makedirs(egg.scriptsdir)

    for line in egg.iter_files_to_install():
        arcname, action = line.split()
        logger.info("arcname=%r    action=%r", arcname, action)

        if action == 'PROXY':
            ei = 'EGG-INFO/'
            if arcname.startswith(ei):
                src = abspath(join(egg.meta_dir, arcname[len(ei):]))
            else:
                src = abspath(join(egg.prefix, arcname))
            logger.info("     src: %r", src)
            egg.files.extend(_create_proxy(src, egg.scriptsdir, pythonexe))
        else:
            data = egg.z.read(arcname)
            dst = abspath(join(egg.prefix, action, basename(arcname)))
            logger.info("     dst: %r", dst)
            rm_rf(dst)
            with open(dst, 'wb') as fo:
                fo.write(data)
            egg.files.append(dst)


def fix_script(path, pythonexe=sys.executable):
    """
    Fixes the shebang (or equivalent) of the given script.
    """
    if islink(path) or not isfile(path):
        return

    with open(path, "rb") as fi:
        data = fi.read()

    try:
        data = data.decode("utf8")
    except UnicodeDecodeError:
        return

    if ' egginst ' in data:
        # This string is in the comment when write_script() creates
        # the script, so there is no need to fix anything.
        return

    m = hashbang_pat.match(data)
    if not (m and 'python' in m.group().lower()):
        return

    python = _get_executable(pythonexe, with_quotes=on_win)
    new_data = hashbang_pat.sub('#!' + python.replace('\\', '\\\\'),
                                data, count=1)
    if new_data == data:
        return
    logger.info("Updating: %r", path)

    with open(path, 'wb') as fo:
        fo.write(new_data.encode("utf8"))

    os.chmod(path, 0o755)


def fix_scripts(egg):
    for path in egg.files:
        if path.startswith(egg.scriptsdir):
            fix_script(path)


def _get_executable(executable=sys.executable, pythonw=False,
                    with_quotes=False):
    res = executable
    if on_win:
        # sys.executable may actually be pythonw.exe in order to avoid
        # popping up a cmd shell during install.
        p = re.compile(r'pythonw?\.exe', re.I)
        res = p.sub('pythonw.exe' if pythonw else 'python.exe', res)
    if with_quotes:
        res = '"%s"' % res
    return res


def _write_exe(dst, kind="console_script"):
    """
    This function is only used on Windows.   It either writes cli.exe or
    gui.exe to the destination specified, depending on script_type.

    The binary content of these files are read from the module exe_data,
    which may be generated by the following small script (run from the
    setuptools directory which contains the file cli.exe and gui.exe:
    fo = open('exe_data.py', 'w')
    for name in ['cli', 'gui']:
        data = open('%s.exe' % name, 'rb').read()
        fo.write('%s = %r\n' % (name, data))
    fo.close()
    """
    if kind == "gui_script":
        data = gui
    elif kind == "console_script":
        data = cli
    else:
        msg = "Did not expect entry point kind {0!r}".format(kind)
        raise Exception(msg)

    rm_rf(dst)
    try:
        with open(dst, 'wb') as fp:
            fp.write(data)
    except IOError:
        # When bootstrapping, the file egginst.exe is in use and can therefore
        # not be rewritten, which is OK since its content is always the same.
        pass
    os.chmod(dst, 0o755)


def _create_proxy(src, bin_dir, executable=sys.executable):
    """
    create a proxy of src in bin_dir (Windows only)
    """
    logger.info("Creating proxy executable to: %r", src)
    assert src.endswith('.exe')

    dst_name = basename(src)
    if dst_name.startswith('epd-'):
        dst_name = dst_name[4:]

    dst = join(bin_dir, dst_name)
    _write_exe(dst)

    dst_script = dst[:-4] + '-script.py'
    rm_rf(dst_script)

    with open(dst_script, 'w') as fo:
        fo.write('''\
#!"%(python)s"
# This proxy was created by egginst from an egg with special instructions
#
import sys
import subprocess

src = %(src)r

sys.exit(subprocess.call([src] + sys.argv[1:]))
''' % dict(python=_get_executable(executable), src=src))
    return dst, dst_script


def _write_script(path, entry_point, template, pythonexe):
    """
    Write an entry point script to path.
    """
    logger.info('Creating script: %s', path)

    rm_rf(path)

    with open(path, 'w') as fo:
        data = template.format(
            python=_get_executable(
                pythonexe, pythonw=path.endswith('.pyw'),
                with_quotes=on_win
            ),
            module=entry_point.module, func=entry_point.function
        )
        fo.write(data)

    os.chmod(path, 0o755)


class _EntryPoint(object):
    """ Simple object representing an entry point."""
    @classmethod
    def from_string(cls, name, s):
        """ Create an new entry point from its name and the 'module:func'
        value as usually found in the entry_point.txt script.
        """
        parts = s.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid entry point string: {0!r}".format(s))
        else:
            return cls(name, parts[0], parts[1])

    def __init__(self, name, module, function):
        self.name = name
        self.module = module
        self.function = function


class ConsoleScript(_EntryPoint):
    kind = "console_script"


class GUIScript(_EntryPoint):
    kind = "gui_script"


_DEFAULT_TEMPLATE = """\
#!{python}
#
if __name__ == '__main__':
    import sys
    from {module} import {func}

    sys.exit({func}())
"""
