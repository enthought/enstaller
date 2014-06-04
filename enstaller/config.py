# Copyright by Enthought, Inc.
# Author: Ilan Schnell <ischnell@enthought.com>
from __future__ import absolute_import, print_function

import base64
import logging
import json
import re
import urlparse
import os
import sys
import textwrap
import platform
import tempfile
import urllib2
import warnings

from getpass import getpass
from os.path import isfile, join

from egginst.utils import parse_assignments

from enstaller.vendor import keyring
from enstaller.vendor.keyring.backends.file import PlaintextKeyring

from enstaller import __version__
from enstaller.errors import (
    AuthFailedError, EnpkgError, EnstallerException, InvalidConfiguration)
from enstaller import plat
from .utils import PY_VER, abs_expanduser, fill_url


logger = logging.getLogger(__name__)


_INDEX_NAME = "index.json"


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


KEYRING_SERVICE_NAME = 'Enthought.com'


def under_venv():
    return hasattr(sys, "real_prefix")


def real_prefix():
    if under_venv():
        return sys.real_prefix
    else:
        return sys.prefix


ENSTALLER4RC_FILENAME = ".enstaller4rc"
SYS_PREFIX_ENSTALLER4RC = os.path.join(real_prefix(), ENSTALLER4RC_FILENAME)
HOME_ENSTALLER4RC = os.path.join(abs_expanduser("~"), ENSTALLER4RC_FILENAME)


def configuration_read_search_order():
    """
    Return a list of directories where to look for the configuration file.
    """
    paths = [
        abs_expanduser("~"),
        real_prefix(),
    ]

    return [os.path.normpath(p) for p in paths]


def add_url(filename, config, url):
    url = fill_url(url)
    if url in config.IndexedRepos:
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
           'Using a temporary cache for index and eggs.\n'.format(local_dir))
    return tempfile.mkdtemp()


RC_TMPL = """\
# enstaller configuration file
# ============================
#
# This file contains the default package repositories and configuration
# used by enstaller %(version)s for the Python %(py_ver)s environment:
#
#   sys.prefix = %(sys_prefix)r
#
# This file was initially created by running the enpkg command.

%(auth_section)s

# `use_webservice` refers to using 'https://api.enthought.com/eggs/'.
# The default is True; that is, the webservice URL is used for fetching
# eggs.  Uncommenting changes this behavior to using the explicit
# IndexedRepos listed below.
#use_webservice = False

# When use_webservice is True, one can control the store entry point enpkg will
# talk to. If not specified, a default will be used. Mostly useful for testing
#store_url = "https://acme.com"

# The enpkg command searches for eggs in the list `IndexedRepos` defined
# below.  When enpkg searches for an egg, it tries each repository in
# this list in order and selects the first one that matches, ignoring
# remaining repositories.  Therefore, the order of this list matters.
#
# For local repositories, the index file is optional.  Remember that on
# Windows systems backslashes in a directory path need to escaped, e.g.:
# r'file://C:\\repository\\' or 'file://C:\\\\repository\\\\'
IndexedRepos = [
#  'https://www.enthought.com/repo/ets/eggs/{SUBDIR}/',
  'https://www.enthought.com/repo/epd/GPL-eggs/{SUBDIR}/',
  'https://www.enthought.com/repo/epd/eggs/{SUBDIR}/',
# The Enthought PyPI build mirror:
  'http://www.enthought.com/repo/pypi/eggs/{SUBDIR}/',
]

# Install prefix (enpkg --prefix and --sys-prefix options overwrite
# this).  When this variable is not provided, it will default to the
# value of sys.prefix (within the current interpreter running enpkg).
#prefix = %(sys_prefix)r

# When running enpkg behind a firewall it might be necessary to use a
# proxy to access the repositories.  The URL for the proxy can be set
# here.  Note that the enpkg --proxy option will overwrite this setting.
%(proxy_line)s

# Uncomment the next line to disable application menu-item installation.
# This only affects the few packages that install menu items, such as
# IPython.
#noapp = True

# Uncomment the next line to turn off automatic prompts to update
# enstaller.
#autoupdate = False

# Uncomment to disable pypi eggs
#use_pypi = False
"""


def _decode_auth(s):
    parts = base64.decodestring(s).split(":")
    if len(parts) == 2:
        return tuple(parts)
    else:
        raise InvalidConfiguration("Invalid auth line")


def _encode_auth(username, password):
    s = "{0}:{1}".format(username, password)
    return base64.encodestring(s).rstrip()


def write_default_config(filename):
    if os.path.isfile(filename):
        msg = "File '{0}' already exists, not overwriting."
        raise EnstallerException(msg.format(filename))
    else:
        config = Configuration()
        config.write(filename)


def _is_using_epd_username(filename_or_fp):
    """
    Returns True if the given configuration file uses EPD_username.
    """
    data = parse_assignments(filename_or_fp)
    return "EPD_username" in data and not "EPD_auth" in data


def convert_auth_if_required(filename):
    """
    This function will convert configuration using EPD_username + keyring to
    using EPD_auth.

    Returns True if the file has been modified, False otherwise.
    """
    did_convert = False
    if _is_using_epd_username(filename):
        config = Configuration.from_file(filename)
        username = config.EPD_username
        password = _get_keyring_password(username)
        if password is None:
            raise EnpkgError("Cannot convert password: no password found in keyring")
        else:
            config.set_auth(username, password)
            config._change_auth(filename)
            did_convert = True

    return did_convert


def _get_keyring_password(username):
    return keyring.get_password(KEYRING_SERVICE_NAME, username)

def _set_keyring_password(username, password):
    return keyring.set_password(KEYRING_SERVICE_NAME, username, password)

class Configuration(object):
    @classmethod
    def _get_default_config(cls):
        config_filename = get_path()
        if config_filename is None:
            raise InvalidConfiguration("No default configuration found.")
        else:
            return cls.from_file(config_filename)

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
        accepted_keys_as_is = set([
            "proxy", "noapp", "use_webservice", "autoupdate",
            "prefix", "IndexedRepos", "repository_cache", "use_pypi",
            "store_url",
        ])

        def _create(fp):
            ret = cls()
            for k, v in parse_assignments(fp).iteritems():
                if k in accepted_keys_as_is:
                    setattr(ret, k, v)
                elif k == "EPD_auth":
                    username, password = _decode_auth(v)
                    ret._username = username
                    ret._password = password
                elif k == "EPD_username":
                    ret._username = v
                    if keyring is None:
                        ret._password = None
                    else:
                        ret._password = _get_keyring_password(v)
                else:
                    warnings.warn("Unsupported configuration setting {0}, "
                                  "ignored".format(k))
            return ret

        if isinstance(filename, basestring):
            with open(filename, "r") as fp:
                ret = _create(fp)
                ret._filename = filename
                return ret
        else:
            return _create(filename)

    def __init__(self):
        self.proxy = None
        self.noapp = False
        self.use_webservice = True
        self.autoupdate = True
        self.use_pypi = True

        self._prefix = sys.prefix
        self._IndexedRepos = []
        self.store_url = "https://api.enthought.com"

        self._repository_cache = join(sys.prefix, 'LOCAL-REPO')

        self._username = None
        self._password = None

        self._filename = None

    @property
    def webservice_entry_point(self):
        return fill_url("{0}/eggs/{1}/".format(self.store_url, plat.custom_plat))

    @property
    def api_url(self):
        return fill_url("{0}/accounts/user/info/".format(self.store_url))

    @property
    def filename(self):
        """
        The filename this configuration was created from.

        May be None if the configuration was not created from a file.
        """
        return self._filename

    def set_auth(self, username, password):
        if username is None or password is None:
            raise InvalidConfiguration(
                "invalid authentication arguments: "
                "{0}:{1}".format(username, password))
        else:
            self._username = username
            self._password = password

    def reset_auth(self):
        self._username = None
        self._password = None

    def get_auth(self):
        return (self._username, self._password)

    def _ensure_keyring_is_set(self):
        """
        Store current password in keyring, but only if not set already, or if
        the password has changed.

        It is an error to call this if username or password are not set.
        """
        assert self.is_auth_configured, "username/password must be set !"
        if _get_keyring_password(self._username) is None \
           or _get_keyring_password(self._username) != self._password:
            _set_keyring_password(self._username, self._password)

    def write(self, filename):
        username, password = self.get_auth()
        if username and password:
            authline = 'EPD_auth = %r' % self.EPD_auth
            auth_section = textwrap.dedent("""
            # A Canopy / EPD subscriber authentication is required to access the
            # Canopy / EPD repository.  To change your credentials, use the 'enpkg
            # --userpass' command, which will ask you for your email address
            # password.
            %s
            """ % authline)
        else:
            auth_section = ''

        if self.proxy:
            proxy_line = 'proxy = %r' % self.proxy
        else:
            proxy_line = ('#proxy = <proxy string>  '
                          '# e.g. "http://<user>:<passwd>@123.0.1.2:8080"')

        variables = {"py_ver": PY_VER, "sys_prefix": sys.prefix, "version": __version__,
                     "proxy_line": proxy_line, "auth_section": auth_section}
        with open(filename, "w") as fo:
            fo.write(RC_TMPL % variables)

    def _change_auth(self, filename):
        pat = re.compile(r'^(EPD_auth|EPD_username)\s*=.*$', re.M)
        with open(filename, 'r') as fi:
            data = fi.read()

        if not self.is_auth_configured:
            if pat.search(data):
                data = pat.sub("", data)
            with open(filename, 'w') as fo:
                fo.write(data)
            return

        authline = 'EPD_auth = %r' % self.EPD_auth

        if pat.search(data):
            data = pat.sub(authline, data)
        else:
            lines = data.splitlines()
            lines.append(authline)
            data = '\n'.join(lines) + '\n'

        with open(filename, 'w') as fo:
            fo.write(data)

    def _checked_change_auth(self, filename):
        if not self.is_auth_configured:
            raise InvalidConfiguration("No auth configured: cannot "
                                       "change auth.")
        user = {}

        user = authenticate(self)
        self._change_auth(filename)
        print(subscription_message(self, user))
        return user

    @property
    def is_auth_configured(self):
        """
        Returns True if authentication is set up for this configuration object.

        Note
        ----
        This only checks whether the auth is configured, not whether the
        authentication information is correct.
        """
        if self._username and self._password:
            return True
        else:
            return False

    @property
    def prefix(self):
        return self._prefix

    @prefix.setter
    def prefix(self, value):
        self._prefix = abs_expanduser(value)

    @property
    def repository_cache(self):
        return self._repository_cache

    @repository_cache.setter
    def repository_cache(self, value):
        self._repository_cache = _get_writable_local_dir(abs_expanduser(value))
        return self._repository_cache

    @property
    def IndexedRepos(self):
        return self._IndexedRepos

    @IndexedRepos.setter
    def IndexedRepos(self, urls):
        self._IndexedRepos = [fill_url(url) for url in urls]

    @property
    def EPD_username(self):
        return self._username

    @EPD_username.setter
    def EPD_username(self, value):
        self._username = value

    @property
    def EPD_auth(self):
        if not self.is_auth_configured:
            raise InvalidConfiguration("EPD_auth is not available when "
                                       "auth has not been configured.")
        return _encode_auth(self._username, self._password)

    @EPD_auth.setter
    def EPD_auth(self, value):
        try:
            username, password = _decode_auth(value)
        except Exception:
            raise InvalidConfiguration("Invalid EPD_auth value")
        else:
            self._username = username
            self._password = password


def get_auth():
    warnings.warn("get_auth deprecated, use Configuration.get_auth instead",
                  DeprecationWarning)
    if get_path() is None:
        raise InvalidConfiguration(
            "No enstaller configuration found, no "
            "authentication information available")
    return Configuration._get_default_config().get_auth()


def get_path():
    """
    Return the absolute path to the config file.
    """
    warnings.warn("get_path deprecated, use Configuration.from_filename "
                  "with an explicit filename", DeprecationWarning)
    for p in configuration_read_search_order():
        path = os.path.join(p, ENSTALLER4RC_FILENAME)
        if isfile(path):
            return path
    return None


def input_auth():
    """
    Prompt user for username and password.  Return (username, password)
    tuple or (None, None) if left blank.
    """
    print(textwrap.dedent("""\
        Please enter the email address and password for your Canopy / EPD
        subscription.  """))
    username = raw_input('Email (or username): ').strip()
    if not username:
        return None, None
    return username, getpass('Password: ')


def _web_auth(auth, api_url):
    """
    Authenticate a user's credentials (an `auth` tuple of username,
    password) using the web API.  Return a dictionary containing user
    info.

    Function taken from Canopy and modified.
    """
    # Make basic local checks
    username, password = auth
    if username is None or password is None:
        raise AuthFailedError("Authentication error: User login is required.")

    # Authenticate with the web API
    auth = 'Basic ' + (':'.join(auth).encode('base64').strip())
    req = urllib2.Request(api_url, headers={'Authorization': auth})

    try:
        f = urllib2.urlopen(req)
    except urllib2.URLError as e:
        raise AuthFailedError("Authentication error: %s" % e.reason)

    try:
        res = f.read()
    except urllib2.HTTPError as e:
        raise AuthFailedError("Authentication error: %s" % e.reason)

    # See if web API refused to authenticate
    user = json.loads(res)
    if not(user['is_authenticated']):
        raise AuthFailedError('Authentication error: Invalid user login.')

    return user


def subscription_level(user):
    """
    Extract the subscription level from the dictionary (`user`) returned by the
    web API.
    """
    if 'has_subscription' in user:
        if user.get('is_authenticated', False) and user.get('has_subscription', False):
            return 'Canopy / EPD Basic or above'
        elif user.get('is_authenticated', False) and not(user.get('has_subscription', False)):
            return 'Canopy / EPD Free'
        else:
            return None
    else:  # don't know the subscription level
        if user.get('is_authenticated', False):
            return 'Canopy / EPD'
        else:
            return None


def subscription_message(config, user):
    """
    Return a 'subscription level' message based on the `user`
    dictionary.

    `user` is a dictionary, probably retrieved from the web API, that
    may contain `is_authenticated`, and `has_subscription`.
    """
    message = ""

    if user.get('is_authenticated', False):
        username, password = config.get_auth()
        login = "You are logged in as %s" % username
        subscription = "Subscription level: %s" % subscription_level(user)
        name = user.get('first_name', '') + ' ' + user.get('last_name', '')
        name = name.strip()
        if name:
            name = ' (' + name + ')'
        message = login + name + '.\n' + subscription
    else:
        message = "You are not logged in.  To log in, type 'enpkg --userpass'."

    return message


def prepend_url(filename, url):
    f = open(filename, 'r+')
    data = f.read()
    pat = re.compile(r'^IndexedRepos\s*=\s*\[\s*$', re.M)
    if not pat.search(data):
        sys.exit("Error: IndexedRepos section not found")
    data = pat.sub(r"IndexedRepos = [\n  '%s'," % url, data)
    f.seek(0)
    f.write(data)
    f.close()


def _head_request(url, auth=None):
    if auth:
        auth = 'Basic ' + (':'.join(auth).encode('base64').strip())
        request = urllib2.Request(url)
        request.add_unredirected_header("Authorization", auth)
    else:
        request = urllib2.Request(url)
    request.get_method = lambda : 'HEAD'

    return urllib2.urlopen(request)


def authenticate(configuration):
    """
    Attempt to authenticate the user's credentials by the appropriate
    means.

    If 'use_webservice' is set, authenticate with the web API and return
    a dictionary containing user info on success.

    Else, authenticate with the configured repositories in config.IndexedRepos
    return a dict containing is_authenticated=True on success.

    If authentication fails, raise an exception.
    """
    if not configuration.is_auth_configured:
        raise EnstallerException("No valid auth information in "
                                 "configuration, cannot authenticate.")

    user = {}
    auth = configuration.get_auth()

    if configuration.use_webservice:
        # check credentials using web API
        try:
            user = _web_auth(auth, configuration.api_url)
            assert user['is_authenticated']
        except Exception as e:
            raise AuthFailedError('Authentication failed: %s.' % e)
    else:
        for url in configuration.IndexedRepos:
            parse = urlparse.urlparse(url)
            if parse.scheme in ("http", "https"):
                index = url + _INDEX_NAME
                try:
                    _head_request(index, auth)
                except urllib2.HTTPError as e:
                    http_code = e.getcode()
                    if http_code in (401, 403):
                        msg = "Authentication error: {0!r}".format(e.reason)
                        raise AuthFailedError(msg)
                    elif http_code == 404:
                        msg = "Could not access repo {0!r} (error: {1!r})". \
                                format(index, e.msg)
                        raise InvalidConfiguration(msg)
                    else:
                        raise
        user = dict(is_authenticated=True)

    return user


def print_config(config, prefix):
    print("Python version:", PY_VER)
    print("enstaller version:", __version__)
    print("sys.prefix:", sys.prefix)
    print("platform:", platform.platform())
    print("architecture:", platform.architecture()[0])
    print("use_webservice:", config.use_webservice)
    if config.filename is not None:
        print("config file:", config.filename)
    print("keyring backend: %s" % (_keyring_backend_name(),))
    print("settings:")
    print("    prefix = %s" % prefix)
    print("    %s = %s" % ("repository_cache", config.repository_cache))
    print("    %s = %r" % ("noapp", config.noapp))
    print("    %s = %r" % ("proxy", config.proxy))
    print("    IndexedRepos:", '(not used)' if config.use_webservice else '')
    for repo in config.IndexedRepos:
        print('        %r' % repo)

    user = {}
    try:
        user = authenticate(config)
    except Exception as e:
        print(e)
    print(subscription_message(config, user))
