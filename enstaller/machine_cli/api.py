import json
import os.path
import subprocess

from enstaller.auth import UserPasswordAuth
from enstaller.errors import ProcessCommunicationError


class SubprocessEnpkgExecutor(object):
    def __init__(self, python_path, store_url, auth, repositories,
                 repository_cache):
        """ This class allows manipulating runtimes' enpkg using subprocesses.
        """
        self.python_path = python_path

        self.store_url = store_url
        self.auth = auth
        self.repositories = repositories
        self.repository_cache = repository_cache

    def _auth_to_json(self, auth):
        if isinstance(auth, UserPasswordAuth):
            return {"kind": "simple",
                    "username": auth.username,
                    "password": auth.password}
        else:
            raise ValueError()

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
        json_data = {
            "authentication": self._auth_to_json(self.auth),
            "files_cache": self.repository_cache,
            "repositories": self.repositories,
            "requirement": requirement_string,
            "store_url": self.store_url,
        }

        return self._run_command("install", json_data)

    def remove(self, package_name):
        json_data = {
            "authentication": self._auth_to_json(self.auth),
            "files_cache": self.repository_cache,
            "repositories": self.repositories,
            "requirement": package_name,
            "store_url": self.store_url,
        }

        return self._run_command("remove", json_data)

    def update_all(self):
        json_data = {
            "authentication": self._auth_to_json(self.auth),
            "files_cache": self.repository_cache,
            "repositories": self.repositories,
            "store_url": self.store_url,
        }

        return self._run_command("update_all", json_data)
