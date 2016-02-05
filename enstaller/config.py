# Copyright by Enthought, Inc.
# Author: Ilan Schnell <ischnell@enthought.com>
from __future__ import absolute_import, print_function

import logging
import re
import os
import sys
import platform
import tempfile
import warnings

from os.path import isfile, join

from egginst.utils import parse_assignments
from egginst.vendor.six import string_types
from egginst.vendor.six.moves import urllib

from enstaller.vendor import keyring
from enstaller.vendor.keyring.backends.file import PlaintextKeyring

from enstaller import __version__
from enstaller.auth import (_INDEX_NAME, DUMMY_USER,
                            subscription_message, APITokenAuth, UserInfo,
                            UserPasswordAuth)
from enstaller.config_templates import RC_DEFAULT_TEMPLATE, RC_TEMPLATE
from enstaller.errors import (EnstallerException, InvalidConfiguration,
                              InvalidFormat)
from enstaller.proxy_info import ProxyInfo
from enstaller.utils import fill_template_path, real_prefix, under_venv
from enstaller.vendor import requests
from enstaller.cli.utils import humanize_ssl_error_and_die
from enstaller import plat
from .utils import PY_VER, abs_expanduser, fill_url
from ._yaml_config import load_configuration_from_yaml

logger = logging.getLogger(__name__)

KEYRING_SERVICE_NAME = 'Enthought.com'

ENSTALLER4RC_FILENAME = ".enstaller4rc"
SYS_PREFIX_ENSTALLER4RC = os.path.join(sys.prefix, ENSTALLER4RC_FILENAME)
HOME_ENSTALLER4RC = os.path.join(abs_expanduser("~"), ENSTALLER4RC_FILENAME)

STORE_KIND_LEGACY = "legacy"
STORE_KIND_BROOD = "brood"
_BROOD_PREFIX = "brood+"


def _setup_keyring():
    backend = PlaintextKeyring()

    try:
        if sys.platform == "win32":
            from enstaller.vendor.keyring.backends.Windows import \
                WinVaultKeyring
            tentative_backend = WinVaultKeyring()
        elif sys.platform == "darwin":
            from enstaller.vendor.keyring.backends.OS_X import Keyring
            tentative_backend = Keyring()
        else:
            tentative_backend = backend
        if tentative_backend.priority >= 0:
            backend = tentative_backend
    except ImportError:
        pass

    keyring.set_keyring(backend)

_setup_keyring()


def _keyring_backend_name():
    return str(type(keyring.get_keyring()))


def legacy_configuration_read_search_order():
    """
    Return a list of directories where to look for the configuration file.

    Legacy order, don't use outside canopy.
    """
    paths = [
        abs_expanduser("~"),
        real_prefix(),
    ]

    return [os.path.normpath(p) for p in paths]


def configuration_read_search_order():
    """
    Return a list of directories where to look for the configuration file.
    """
    paths = [sys.prefix]
    paths.append(abs_expanduser("~"))
    if under_venv():
        paths.append(real_prefix())

    return [os.path.normpath(p) for p in paths]


def add_url(filename, config, url):
    url = fill_url(url)
    if url in config.indexed_repositories:
        print("Already configured:", url)
        return
    prepend_url(filename, url)


def _get_writable_local_dir(local_dir):
    if not os.access(local_dir, os.F_OK):
        try:
            os.makedirs(local_dir)
            return local_dir
        except (OSError, IOError):
            pass
    elif os.access(local_dir, os.W_OK):
        return local_dir

    logger.warn('Warning: the following directory is not writeable '
                'with current permissions:\n'
                '    {0!r}\n'
                'Using a temporary cache for index and eggs.\n'.
                format(local_dir))
    return tempfile.mkdtemp()


def write_default_config(filename):
    """
    Write a default configuration file at the given location.

    Will raise an exception if a file already exists.

    Parameters
    ----------
    filename : str
        The location to write to.
    """
    if os.path.isfile(filename):
        msg = "File '{0}' already exists, not overwriting."
        raise EnstallerException(msg.format(filename))
    else:
        config = Configuration()

        if config.proxy:
            proxy_line = 'proxy = %r' % str(config.proxy)
        else:
            proxy_line = ('#proxy = <proxy string>  '
                          '# e.g. "http://<user>:<passwd>@123.0.1.2:8080"')

        variables = {"py_ver": PY_VER, "sys_prefix": sys.prefix, "version":
                     __version__, "proxy_line": proxy_line,
                     "auth_section": ""}
        with open(filename, "w") as fo:
            fo.write(RC_DEFAULT_TEMPLATE % variables)


def _is_using_epd_username(filename_or_fp):
    """
    Returns True if the given configuration file uses EPD_username.
    """
    data = parse_assignments(filename_or_fp)
    return "EPD_username" in data and "EPD_auth" not in data


def convert_auth_if_required(filename):
    """
    This function will convert configuration using EPD_username + keyring to
    using EPD_auth.

    Returns True if the file has been modified, False otherwise.
    """
    did_convert = False
    if _is_using_epd_username(filename):
        msg = "Cannot convert password: no password found in keyring"
        config = Configuration.from_file(filename)
        if config.auth is None:
            raise EnstallerException(msg)
        username = config.auth.username
        password = _get_keyring_password(username)
        if password is None:
            raise EnstallerException(msg)
        else:
            config.update(auth=(username, password))
            config._change_auth(filename)
            did_convert = True

    return did_convert


def _get_keyring_password(username):
    return keyring.get_password(KEYRING_SERVICE_NAME, username)


def _set_keyring_password(username, password):
    return keyring.set_password(KEYRING_SERVICE_NAME, username, password)


def _create_error_message(fp, exc):
    pos = fp.tell()
    try:
        fp.seek(0)
        lines = fp.readlines()
        line = lines[exc.lineno-1].rstrip()
        if isinstance(exc, SyntaxError):
            msg = "Could not parse configuration file " \
                  "(invalid python syntax at line {0!r}: expression {1!r})".\
                  format(exc.lineno, line)
        else:
            msg = "Could not parse configuration file " \
                  "(error at line {0!r}: expression {1!r} not " \
                  "supported)".format(exc.lineno, line)
        return msg
    finally:
        fp.seek(pos)


class Configuration(object):
    @classmethod
    def _from_legacy_locations(cls):
        warnings.warn("Using legacy location is deprecated, use "
                      "Configuration.from_filename with an explicit "
                      "filename instead", DeprecationWarning)
        config_path = None
        for p in legacy_configuration_read_search_order():
            candidate = os.path.join(p, ENSTALLER4RC_FILENAME)
            if isfile(candidate):
                config_path = candidate
                break

        if config_path is None:
            raise InvalidConfiguration("No default configuration found.")
        else:
            return cls.from_file(config_path)

    @classmethod
    def from_yaml_filename(cls, filename):
        return load_configuration_from_yaml(cls, filename)

    @classmethod
    def from_file(cls, filename):
        """
        Create a new Configuration instance from the given file.

        Parameters
        ----------
        filename: str or file-like object
            If a string, is understood as a filename to open. Understood as a
            file-like object otherwise.
        """
        def _create(fp):
            ret = cls()

            def api_token_to_auth(api_token):
                ret.update(auth=APITokenAuth(api_token))

            def epd_auth_to_auth(epd_auth):
                ret.update(auth=UserPasswordAuth.from_encoded_auth(epd_auth))

            def epd_username_to_auth(username):
                if keyring is not None:
                    password = _get_keyring_password(username)
                    if password is not None:
                        ret.update(auth=(username, password))

            try:
                parsed = parse_assignments(fp)
            except (InvalidFormat, SyntaxError) as e:
                msg = _create_error_message(fp, e)
                raise InvalidConfiguration(msg)

            # We need a custom translator to manage attributes in the
            # configuration file without polluting the config class
            translator = ret._name_to_setter.copy()
            translator.update({
                "EPD_auth": epd_auth_to_auth,
                "EPD_username": epd_username_to_auth,
                "IndexedRepos": translator["indexed_repositories"],
                "api_token": api_token_to_auth,
            })

            if "EPD_auth" in parsed and "api_token" in parsed:
                msg = "Both 'EPD_auth' and 'api_token' set in configuration." \
                      "\nYou should remove one of those for consistent " \
                      "behaviour."
                warnings.warn(msg)

            for name, value in parsed.items():
                if name in translator:
                    translator[name](value)
                else:
                    warnings.warn("Unsupported configuration setting {0}, "
                                  "ignored".format(name))
            return ret

        if isinstance(filename, string_types):
            with open(filename, "r") as fp:
                ret = _create(fp)
                ret._filename = filename
                return ret
        else:
            return _create(filename)

    def __init__(self, **kw):
        """ Create a new configuration instance.

        Any argument passed to the constructor need to be a keyword argument,
        and is understood as an argument to the update method, e.g.::

            config = Configuration(store_url="http://acme.com")

            # equivalent to
            config = Configuration()
            config.update(store_url="http://acme.com")
        """
        self._auth = None
        self._autoupdate = True
        self._noapp = False
        self._proxy = None
        self._use_pypi = True
        self._use_webservice = True

        self._prefix = os.path.normpath(sys.prefix)
        self._indexed_repositories = []
        self._store_url = "https://api.enthought.com"
        self._store_kind = STORE_KIND_LEGACY

        self._repository_cache = None

        self._filename = None
        self._platform = plat.custom_plat

        self._max_retries = 0
        self._verify_ssl = True

        self._name_to_setter = {}
        simple_attributes = [
            ("autoupdate", "_autoupdate"),
            ("noapp", "_noapp"),
            ("verify_ssl", "_verify_ssl"),
            ("use_pypi", "_use_pypi"),
            ("use_webservice", "_use_webservice"),
        ]
        for name, private_attribute in simple_attributes:
            self._name_to_setter[name] = \
                self._simple_attribute_set_factory(private_attribute)

        self._name_to_setter.update({
            "auth": self._set_auth,
            "indexed_repositories": self._set_indexed_repositories,
            "max_retries": self._set_max_retries,
            "prefix": self._set_prefix,
            "proxy": self._set_proxy,
            "repository_cache": self._set_repository_cache,
            "store_url": self._set_store_url,
        })

        self.update(**kw)

    # ----------
    # Properties
    # ----------
    @property
    def api_url(self):
        """
        Url to hit to get user information on api.e.com.
        """
        return fill_url("{0}/accounts/user/info/".format(self.store_url))

    @property
    def auth(self):
        """
        The auth object that may be passed to Session.authenticate

        :return: the auth instance, or None is configured.
        :rtype: IAuth or None
        """
        return self._auth

    @property
    def autoupdate(self):
        """
        Whether enpkg should attempt updating itself.
        """
        return self._autoupdate

    @property
    def filename(self):
        """
        The filename this configuration was created from. May be None if the
        configuration was not created from a file.
        """
        return self._filename

    @property
    def indexed_repositories(self):
        """
        List of (old-style) repositories. Only actually used when
        use_webservice is False.
        """
        return self._indexed_repositories

    @property
    def indices(self):
        """
        Returns a list of pair (index_url, store_location) for this given
        configuration.

        Takes into account webservice/no webservice and pypi True/False
        """
        if self.use_webservice:
            index_url = store_url = self.webservice_entry_point + _INDEX_NAME
            if self.use_pypi:
                index_url += "?pypi=true"
            else:
                index_url += "?pypi=false"
            return tuple([(index_url, store_url)])
        else:
            return tuple((url + _INDEX_NAME, url + _INDEX_NAME)
                         for url in self.indexed_repositories)

    @property
    def max_retries(self):
        """
        Max attempts to retry an http connection or re-fetching data whose
        checksum failed.
        """
        return self._max_retries

    @property
    def noapp(self):
        """
        Ignore appinst entries.
        """
        return self._noapp

    @property
    def prefix(self):
        """
        Prefix in which enpkg operates.
        """
        return self._prefix

    @property
    def proxy(self):
        """
        A ProxyInfo instance or None if no proxy is configured.
        """
        return self._proxy

    @property
    def proxy_dict(self):
        """
        A dictionary <scheme>:<proxy_string> that can be used as the proxies
        argument for requests.
        """
        if self._proxy:
            return {self._proxy.scheme: str(self._proxy)}
        else:
            return {}

    @property
    def repository_cache(self):
        """
        Absolute path where eggs will be cached.
        """
        if self._repository_cache is None:
            return join(self.prefix, "LOCAL-REPO")
        else:
            return self._repository_cache

    @property
    def store_kind(self):
        """
        Store kind (brood, legacy canopy, old-repo style).
        """
        return self._store_kind

    @property
    def store_url(self):
        """
        The store url to hit for indices and eggs.
        """
        return self._store_url

    @property
    def verify_ssl(self):
        """
        Whether to verify SSL CA or not.
        """
        return self._verify_ssl

    @property
    def use_pypi(self):
        """
        Whether to load pypi repositories (in `webservice` mode).
        """
        return self._use_pypi

    @property
    def use_webservice(self):
        """
        Whether to use canopy legacy or not.
        """
        return self._use_webservice

    @property
    def webservice_entry_point(self):
        """
        Whether to fetch indices and data (in `webservice` mode).
        """
        return fill_url("{0}/eggs/{1}/".
                        format(self.store_url, self._platform))

    # --------------
    # Public methods
    # --------------
    def reset_auth(self):
        self._auth = None

    def set_auth_from_encoded(self, value):
        try:
            auth = UserPasswordAuth.from_encoded_auth(value)
        except Exception:
            raise InvalidConfiguration("Invalid EPD_auth value")
        else:
            self.update(auth=auth)

    def set_repositories_from_names(self, names):
        """ Set repositories from their names alone, e.g. 'enthought/free'.

        Parameters
        ----------
        names : list
            List of repository names
        """
        repository_urls = []
        for name in names:
            p = urllib.parse.urlparse(name)
            if p.scheme == "":
                url = self.store_url + "/repo/{0}/{{PLATFORM}}".format(name)
            elif p.scheme == "file":
                url = name
            else:
                msg = "Unsupported syntax: {0!r}".format(name)
                raise InvalidConfiguration(msg)
            repository_urls.append(url)
        self.update(indexed_repositories=repository_urls)

    def update(self, **kw):
        """ Set configuration attributes given as keyword arguments."""
        for name, value in kw.items():
            setter = self._name_to_setter.get(name, None)
            if name is None:
                raise ValueError("Invalid setting name: {0!r}".format(name))
            else:
                setter(value)

    def write(self, filename):
        """ Write this configuration to the given filename.

        Parameters
        ----------
        filename : str
            The path of the written file.
        """
        if self.auth is None:
            auth_section = ""
        else:
            auth_section = self.auth.config_string

        if self.proxy:
            proxy_line = 'proxy = %r' % str(self.proxy)
        else:
            proxy_line = ('#proxy = <proxy string>  '
                          '# e.g. "http://<user>:<passwd>@123.0.1.2:8080"')

        # XXX: because setting indexed repositories use string replacement
        # (sigh...), we need to write the IndexedRepos section in a very specific
        # way:
        #
        #     IndexedRepos = [
        #        url1,
        #        url2
        #    ]
        indexed_repos_string = "\n".join("    %r," % (repo,)
                                         for repo in self.indexed_repositories)

        if self.store_kind == STORE_KIND_BROOD:
            store_url = _BROOD_PREFIX + self.store_url
        else:
            store_url = self.store_url

        variables = {"py_ver": PY_VER, "sys_prefix": sys.prefix, "version":
                     __version__, "proxy_line": proxy_line, "auth_section":
                     auth_section, "store_url": store_url,
                     "indexed_repositories": indexed_repos_string,
                     "use_pypi": self.use_pypi,
                     "use_webservice": self.use_webservice,
                     }
        with open(filename, "w") as fo:
            fo.write(RC_TEMPLATE % variables)

    # ---------------
    # Private methods
    # ---------------
    def _change_auth(self, filename):
        if self.auth is None:
            pat = re.compile(r'^(EPD_auth|EPD_username)\s*=.*$', re.M)

            with open(filename, 'r') as fi:
                data = fi.read()

            if pat.search(data):
                data = pat.sub("", data)

            with open(filename, 'w') as fo:
                fo.write(data)
        else:
            self.auth.change_auth(filename)

    def _checked_change_auth(self, auth, session, filename):
        user = {}

        session.authenticate(auth)
        self.update(auth=auth)
        self._change_auth(filename)

        user = UserInfo.from_session(session)
        print(subscription_message(self, user))
        return user

    def _set_auth(self, auth):
        """ Set the internal authentication information.

        Parameters
        ----------
        auth : Auth-like
            The authentication information. May be a (username, password)
            tuple, or an *Auth subclass.
        """
        if isinstance(auth, tuple) and len(auth) == 2:
            username, password = auth
            if username is None:
                raise InvalidConfiguration(
                    "invalid authentication arguments: "
                    "{0}:{1}".format(username, password))
            self._auth = UserPasswordAuth(username, password)
        else:
            self._auth = auth

    def _set_indexed_repositories(self, urls):
        self._indexed_repositories = tuple(fill_url(url) for url in urls)

    def _set_max_retries(self, raw_max_retries):
        try:
            max_retries = int(raw_max_retries)
        except ValueError:
            msg = "Invalid type for 'max_retries': {0!r}"
            raise InvalidConfiguration(msg.format(raw_max_retries))
        else:
            self._max_retries = max_retries

    def _set_prefix(self, prefix):
        self._prefix = os.path.normpath(abs_expanduser(prefix))

    def _set_proxy(self, proxy_string):
        self._proxy = ProxyInfo.from_string(proxy_string)

    def _set_store_url(self, url):
        p = urllib.parse.urlparse(url)
        if p.scheme.startswith(_BROOD_PREFIX):
            url = url[len(_BROOD_PREFIX):]
            self._store_kind = STORE_KIND_BROOD
        self._store_url = url

    def _set_repository_cache(self, value):
        normalized = fill_template_path(
            os.path.normpath(abs_expanduser(value))
        )
        self._repository_cache = _get_writable_local_dir(normalized)

    def _simple_attribute_set_factory(self, attribute_name):
        return lambda value: setattr(self, attribute_name, value)


def prepend_url(filename, url):
    with open(filename, 'r+') as fp:
        data = fp.read()
        pat = re.compile(r'^IndexedRepos\s*=\s*\[\s*$', re.M)
        if not pat.search(data):
            sys.exit("Error: IndexedRepos section not found")
        data = pat.sub(r"IndexedRepos = [\n  '%s'," % url, data)
        fp.seek(0)
        fp.write(data)


def print_config(config, session):
    print("Python version:", PY_VER)
    print("enstaller version:", __version__)
    print("sys.prefix:", os.path.normpath(sys.prefix))
    print("platform:", platform.platform())
    print("architecture:", platform.architecture()[0])
    print("use_webservice:", config.use_webservice)
    print("autoupdate:", config.autoupdate)
    if config.filename is not None:
        print("config file:", config.filename)
    print("keyring backend: %s" % (_keyring_backend_name(), ))
    print("settings:")
    print("    prefix = %s" % config.prefix)
    print("    %s = %s" % ("repository_cache", config.repository_cache))
    print("    %s = %r" % ("noapp", config.noapp))
    print("    %s = %r" % ("proxy", config.proxy))
    if not config.use_webservice:
        print("    IndexedRepos:")
        for repo in config.indexed_repositories:
            print('        %r' % repo)

    user = DUMMY_USER

    if config.auth is None:
        print("No valid auth information in configuration, cannot "
              "authenticate.")
    else:
        try:
            session.authenticate(config.auth)
            user = UserInfo.from_session(session)
        except requests.exceptions.SSLError as e:
            humanize_ssl_error_and_die(e, config.store_url)
        except Exception as e:
            print(e)
    print(subscription_message(config, user))
