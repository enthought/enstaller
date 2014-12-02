import json
import os.path
import subprocess

from enstaller.errors import ProcessCommunicationError


class SubprocessEnpkgExecutor(object):
    def __init__(self, python_path, store_url, auth, repositories,
                 repository_cache):
        """ This class allows manipulating runtimes' enpkg using subprocesses.

        Parameters
        ----------
        python_path : str
            The absolute path to the python executable to use in subprocesses.
        store_url : str
            The store url (e.g. 'https://acme.com')
        auth : enstaller.auth.IAuth
            The auth credentials to use when connecting to the store
        repositories : list
            List of repositories (e.g. ["enthought/free",
            "enthought/commercial"])
        repository_cache : str
            The path to use to cache downloads.
        """
        self.python_path = python_path

        self.store_url = store_url
        self.auth = auth
        self.repositories = repositories
        self.repository_cache = repository_cache

    def _run_command(self, command, json_data):
        cmd = [self.python_path, "-m", "enstaller.machine_cli.__main__",
               command]

        if not os.path.exists(self.python_path):
            msg = "Runtime's python not found: {0!r}".format(self.python_path)
            raise ValueError(msg)

        json_string = json.dumps(json_data).encode("utf8")

        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        out, _ = p.communicate(json_string)

        if p.returncode != 0:
            msg = "Error while communicating with runtime"
            raise ProcessCommunicationError(msg)

    def install(self, requirement_string):
        """ Install the given requirement

        Parameters
        ----------
        requirement_string: str
            The requirement to install, e.g. 'numpy'
        """
        json_data = {
            "authentication": self.auth.to_config_dict(),
            "files_cache": self.repository_cache,
            "repositories": self.repositories,
            "requirement": requirement_string,
            "store_url": self.store_url,
        }

        return self._run_command("install", json_data)

    def remove(self, package_name):
        """ Remove the given package

        Parameters
        ----------
        package_name: str
            The package to remove
        """
        json_data = {
            "authentication": self.auth.to_config_dict(),
            "files_cache": self.repository_cache,
            "repositories": self.repositories,
            "requirement": package_name,
            "store_url": self.store_url,
        }

        return self._run_command("remove", json_data)

    def update_all(self):
        """ Update every installed package.
        """
        json_data = {
            "authentication": self.auth.to_config_dict(),
            "files_cache": self.repository_cache,
            "repositories": self.repositories,
            "store_url": self.store_url,
        }

        return self._run_command("update_all", json_data)
