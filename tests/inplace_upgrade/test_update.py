#! /bin/sh
import errno
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile

import os.path as op

import pathlib

from fabric.api import lcd, local
from fabric.decorators import task


PY_VER = ".".join(str(part) for part in sys.version_info[:2])

DEFAULT_MASTER_VERSION = "2.0.0.dev1-c9fa3fa"
MASTER_REPO = "https://s3.amazonaws.com/canopy-deployment-server"
SCRIPTS_ROOT = op.abspath(op.dirname(__file__))

MASTER_ROOT = op.abspath(os.getcwd())
ROOT = op.join(MASTER_ROOT, ".test_update")


def _epd_platform():
    """ Determine the EPD platform from platform we're running on.
        Note that we only support 64-bit platforms.
    """
    if sys.platform == "win32":
        return "win-64"
    elif sys.platform.startswith("linux"):
        return "rh5-64"
    elif sys.platform == "darwin":
        return "osx-64"
    else:
        raise RuntimeError("platform %s not supported yet" % sys.platform)


class PythonEnvironment(object):
    def __init__(
            self, install_root, epd_platform=None, master_repo=MASTER_REPO,
            master_root=MASTER_ROOT, scripts_root=SCRIPTS_ROOT):
        self.install_root = install_root
        if epd_platform is None:
            epd_platform = _epd_platform()
        self.epd_platform = epd_platform
        self.master_repo = master_repo
        self.master_root = master_root
        self.scripts_root = scripts_root

        # Make sure that the bin directory of the virtual enviroment
        # is looked up before the normal system path.
        self._prepend_path()

        if sys.platform == "win32":
            self.python = op.join(self.bindir, "python.exe")
            self.easy_install = op.join(self.scriptsdir, "easy_install.exe")
            self.pip = op.join(self.scriptsdir, "pip.exe")
            self.git = "git"
            self.coverage = op.join(self.scriptsdir, "coverage.exe")
            self._enbuild_egg = op.join(self.scriptsdir, "build-egg.exe")
            self._egginst = op.join(self.scriptsdir, "egginst.exe")
        else:
            self.python = op.join(self.bindir, "python")
            self.easy_install = op.join(self.bindir, "easy_install")
            self.pip = op.join(self.bindir, "pip")
            self.git = "git"
            self.coverage = op.join(self.bindir, "coverage")
            self._enbuild_egg = op.join(self.scriptsdir, "build-egg")
            self._egginst = op.join(self.scriptsdir, "egginst")

    @property
    def bindir(self):
        if sys.platform == "win32":
            return op.join(self.install_root)
        else:
            return op.join(self.install_root, "bin")

    @property
    def scriptsdir(self):
        if sys.platform == "win32":
            return op.join(self.bindir, "Scripts")
        else:
            return self.bindir

    def _download_master(self, master):
        import requests
        master_base = op.basename(master)
        url = "{0}/{1}".format(self.master_repo, master_base)
        print "Downloading master from {0}".format(self.master_repo)
        resp = requests.get(url)
        assert resp.status_code == 200

        with open(master_base, "wb") as fp:
            fp.write(resp.content)

    def _prepend_path(self):
        """ Prepends the virtual enviroment binary directories to the $PATH.
        """
        if sys.platform.startswith('win'):
            os.environ['PATH'] = ';'.join((
                op.abspath(self.bindir),
                op.abspath(op.join(self.bindir, 'Scripts')),
                os.environ['PATH']))
        else:
            os.environ['PATH'] = ':'.join((
                op.abspath(self.bindir),
                os.environ['PATH']))

    def init_from_master(self, version, with_activation_scripts=True):
        """ Create a basic python install from an enicab master.
        """
        master_base = _master_path(self.epd_platform, version)
        master = op.join(MASTER_ROOT, master_base)
        if not op.exists(master):
            self._download_master(master)

        _install_master(master, self.install_root)

        if with_activation_scripts:
            self._install_activation_scripts()
        self._fix_custom_tools()

    def destroy(self):
        remove_tree(self.install_root)

    def runpy(self, command, capture=False):
        """ Run the given command locally using the current python interpreter.
        """
        return local("{0} {1}".format(self.python, command), capture=capture)

    def runenpkg(self, command, capture=False):
        """ Run the given command locally using the current python interpreter.
        """
        enpkg = os.path.join(self.scriptsdir, "enpkg")
        return local("{0} {1}".format(enpkg, command), capture=capture)


    def runpip(self, command):
        """ Run the given pip command inside this env
        """
        return local("{0} {1}".format(self.pip, command))


    def bootstrap_setuptools(self):
        """ Install setuptools in this env
        """
        import requests

        target = os.path.join(SCRIPTS_ROOT, "ez_setup.py")

        resp = requests.get("https://bootstrap.pypa.io/ez_setup.py")
        assert resp.status_code == 200

        with open(target, "wb") as fp:
            fp.write(resp.content)

        local("{0} {1} --insecure".format(
            self.python, target))

    def bootstrap_pip(self):
        """ Install pip in this env.
        """
        self.bootstrap_setuptools()
        local("{0} {1}".format(self.easy_install, "pip"))

    def _fix_custom_tools(self):
        """ Fix the master custom_tools package to have a platform variable,
        required by the test infrastructure.
        """
        # FIXME: this should really be fixed in our master
        def _get_custom_tools_path():
            cmd = "-c \"import custom_tools; print custom_tools.__file__\""
            st = local("{0} {1}".format(self.python, cmd), capture=True)
            return op.dirname(st)

        custom_tools_init = op.join(_get_custom_tools_path(), "__init__.py")
        custom_tools_init_bytecode = op.join(
            _get_custom_tools_path(), "__init__.pyc")

        with open(custom_tools_init, "a") as fp:
            fp.write("\nplatform = '{0}'".format(self.epd_platform))
        # FIXME: understand why the bytecode is not updated (python lib treated
        # differently ?)
        os.remove(custom_tools_init_bytecode)


def _install_master(master, target_dir):
    if sys.platform == "win32":
        local(
            "msiexec /a {master} /qn TARGETDIR={target_dir}".format(
                master=master, target_dir=target_dir))
    else:
        local(
            "bash {master} -b -p {target_dir}".format(
                master=master, target_dir=target_dir))


def _master_path(epd_platform, version):
    """ Return the path to the platform specific master.

    """
    template = "master-{version}-{plat}.{extension}"
    return _path_from_template(template, epd_platform, version)


def _path_from_template(template, epd_platform, version):
    arch_bits_to_win_arch = {
        "32": "x86",
        "64": "amd64",
    }

    if sys.platform == "win32":
        extension = "msi"
    elif sys.platform.startswith("linux"):
        extension = "sh"
    elif sys.platform == "darwin":
        extension = "sh"
    else:
        raise RuntimeError("platform %s not supported yet" % sys.platform)

    if sys.platform == "win32":
        bits = epd_platform.split("-")[1]
        plat = arch_bits_to_win_arch[bits]
    else:
        plat = epd_platform
    return template.format(version=version, plat=plat, extension=extension)


def remove_tree(path):
    """ Remove a directory and subdirectories if they exist.

    Parameters
    ----------
    path : string
        The path of the directory to remove.

    """
    if op.exists(path) or op.exists(op.join(pwd(), path)):
        if sys.platform == "win32":
            local("rd /s /q {}".format(path))
        else:
            local("rm -rf {}".format(path))

def listdir(path):
    """ Get the list of files in the path respecting fabric's local directory.

    Parameters
    ----------
    path : string
        The directory for which to get the content list.


    """
    if sys.platform == "win32":
        output = local("dir /b {}".format(path), capture=True)
    else:
        output = local("ls -1 {}".format(path), capture=True)
    return output.splitlines()


def pwd():
    """ Get the current fabric local working directory.

    """
    if sys.platform == "win32":
        cmd = "cd"
    else:
        cmd = "pwd"
    return local(cmd, capture=True).strip()


def makedirs(path):
    """ Create a directory if it exists.

    Parameters
    ----------
    path : string
        The directory to create.

    .. note::
        This is not aware of the local working directory of the fabric script.

    """
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def _generate_egg_index(index_filename, target_egg, forced_version,
                        forced_build):
    with open(target_egg, "rb") as fp:
        md5 = hashlib.md5(fp.read()).hexdigest()

    index_data = {
        os.path.basename(target_egg): {
                "available": True,
                "build": forced_build,
                "md5": md5,
                "mtime": 0.0,
                "name": "enstaller",
                "product": "free",
                "python": None,
                "size": os.stat(target_egg)[stat.ST_SIZE],
                "type": "egg",
                "version": forced_version,
        }
    }

    with open(index_filename, "w") as fp:
        json.dump(index_data, fp, indent=4)

def build_enstaller_egg(forced_version, forced_build=1):
    """ Build an Enthought egg from the current checkout.

    Parameters
    ----------
    forced_version: str
        The version to inject in the egg metadata
    forced_build: int
        The build number to inject in the egg metadata
    """
    environ = os.environ.copy()
    environ["FORCE_ENSTALLER_VERSION"] = forced_version
    subprocess.check_call([sys.executable, "setup.py", "bdist_enegg"],
                          env=environ)

    repo_dir = op.join(ROOT, "repo")

    basename = "enstaller-{}-1.egg".format(forced_version)
    source_egg = os.path.join("dist", basename)
    target_egg = os.path.join(repo_dir, basename)

    makedirs(op.dirname(target_egg))
    os.rename(source_egg, target_egg)

    index_filename = op.join(repo_dir, "index.json")
    _generate_egg_index(index_filename, target_egg, forced_version,
                        forced_build)

    if sys.platform == "win32":
        # XXX: we cannot use as_uri because enstaller does not handle them
        # properly...
        repo_uri = "file://{}/".format(pathlib.Path(repo_dir).as_posix())
    else:
        repo_uri = "file://{}/".format(repo_dir)

    with open(op.join(ROOT, ".enstaller4rc"), "w") as fp:
        fp.write("""\
IndexedRepos = [
    '{}'
]
use_webservice = False
EPD_auth = 'YXNkOmFzZA=='

""".format(repo_uri))

    return target_egg


def _bootstrap_old_enstaller(pyenv, upgrade_from):
    bootstrap = os.path.join("scripts", "bootstrap.py")
    pyenv.runpy("{0} --version {1}".format(bootstrap, upgrade_from))
    m = pyenv.runenpkg("--list", capture=True)
    out = m.stdout
    assert upgrade_from in out


@task
def run_enstaller_upgrade(upgrade_from="4.6.5-1"):
    upgrade_to = "4.8.0"
    # XXX: version lower than 4.6.5 do not seem to handle use_webservice=False
    # correctly when used with --sys-config due to the brain deadness of the
    # old config-as-module-singleton, so we need to start from 4.6.5. The hope
    # is that older versions are similar enough to 4.6.5 as far as inplace
    # upgradeability goes.
    pyenv = PythonEnvironment(ROOT, None)
    pyenv.destroy()

    pyenv.init_from_master(DEFAULT_MASTER_VERSION, False)

    _bootstrap_old_enstaller(pyenv, upgrade_from)

    build_enstaller_egg(upgrade_to)
    with lcd(ROOT):
        local("echo y| {} -m enstaller.main --sys-config -s enstaller".format(pyenv.python))
        # We use --list instead of --version because we overrode the metadata
        # version, not the actualy version in enstaller package
        m = pyenv.runenpkg("--list", capture=True)
        out = m.stdout
        assert upgrade_to in out
