# Copyright by Enthought, Inc.
# Author: Ilan Schnell <ischnell@enthought.com>

import _ast
import ast
import copy
import json
import re
import os
import sys
import platform
import urllib2

from getpass import getpass
from os.path import isfile, join

from enstaller import __version__
from enstaller.errors import AuthFailedError, InvalidConfiguration
from utils import PY_VER, abs_expanduser, fill_url

def __import_new_keyring():
    """
    Import keyring >= 1.1.
    """
    import keyring.backends.OS_X
    import keyring.backends.Gnome
    import keyring.backends.Windows
    import keyring.backends.kwallet

    keyring.core.init_backend()
    if keyring.get_keyring().priority < 0:
        keyring = None
    return keyring

def __import_old_keyring():
    import keyring
    import keyring.backend
    # don't use keyring backends that require console input or just do
    # more or less the same thing we're already doing
    keyring.backend._all_keyring = [keyring.backend.OSXKeychain(),
                                    keyring.backend.GnomeKeyring(),
                                    keyring.backend.KDEKWallet(),
                                    keyring.backend.Win32CryptoKeyring(),
                                    keyring.backend.Win32CryptoRegistry(),
                                    keyring.backend.WinVaultKeyring()]
    keyring.core.init_backend()
    if keyring.get_keyring().supported() < 0:
        keyring = None
    return keyring

try:
    import keyring
except ImportError, KeyError:
    # The KeyError happens when USERPROFILE env var is not defined on windows
    keyring = None
else:
    try:
        keyring = __import_new_keyring()
    except ImportError:
        try:
            keyring = __import_old_keyring()
        except ImportError:
            keyring = None

KEYRING_SERVICE_NAME = 'Enthought.com'

config_fn = ".enstaller4rc"
home_config_path = abs_expanduser("~/" + config_fn)
system_config_path = join(sys.prefix, config_fn)

def get_default_url():
    import plat
    return 'https://api.enthought.com/eggs/%s/' % plat.custom_plat

class PythonConfigurationParser(ast.NodeVisitor):
    def __init__(self):
        self._data = {}

    def parse(self, s):
        self._data.clear()

        root = ast.parse(s)
        self.visit(root)
        return self._data

    def generic_visit(self, node):
        if type(node) != _ast.Module:
            raise ValueError("Unexpected expression @ line {0}".format(node.lineno))
        super(PythonConfigurationParser, self).generic_visit(node)

    def visit_Assign(self, node):
        value = ast.literal_eval(node.value)
        for target in node.targets:
            self._data[target.id] = value

class Configuration(object):
    __keys = (
        'prefix',
        'proxy',
        'noapp',
        'EPD_auth',
        'EPD_username',
        'use_webservice',
        'autoupdate',
        'IndexedRepos',
        'webservice_entry_point',
        'repository_cache',
        'local',
    )

    def __init__(self):
        self.proxy = None
        self.noapp = False
        self.EPD_auth = None
        self.EPD_username = None
        self.use_webservice = True
        self.autoupdate =  True

        self._prefix = sys.prefix
        self._local = join(sys.prefix, 'LOCAL-REPO')
        self._IndexedRepos = []
        self._webservice_entry_point = fill_url(get_default_url())

        self.repository_cache = self.local

    @property
    def local(self):
        return self._local

    @local.setter
    def local(self, value):
        self._local = abs_expanduser(value)

    @property
    def prefix(self):
        return self._prefix

    @prefix.setter
    def prefix(self, value):
        self._prefix = abs_expanduser(value)

    @property
    def IndexedRepos(self):
        return self._IndexedRepos

    @IndexedRepos.setter
    def IndexedRepos(self, urls):
        self._IndexedRepos = [fill_url(url) for url in urls]

    @property
    def webservice_entry_point(self):
        return self._webservice_entry_point

    @webservice_entry_point.setter
    def webservice_entry_point(self, url):
        self._webservice_entry_point = fill_url(url)

    # FIXME: temporary dict protocol emulation as a backward compatibility
    # shim
    def copy(self):
        return copy.copy(self)

    def update(self, data):
        for k in data:
            if k in self.__keys:
                setattr(self, k, data[k])
            else:
                raise KeyError("Invalid key: {0}".format(k))

    def get(self, k, default=None):
        return self[k]

    def __getitem__(self, k):
        if k in self.__keys:
            return getattr(self, k)
        else:
            raise KeyError("Invalid key: {0}".format(k))

    def __iter__(self):
        return iter(self.__keys)

    @property
    def _dict(self):
        return dict((k, self[k]) for k in self.__keys)

def get_path():
    """
    Return the absolute path to the config file.
    """
    if isfile(home_config_path):
        return home_config_path
    if isfile(system_config_path):
        return system_config_path
    return None


def input_auth():
    """
    Prompt user for username and password.  Return (username, password)
    tuple or (None, None) if left blank.
    """
    print """\
Please enter the email address (or username) and password for your
EPD or EPD Free subscription.  If you are not subscribed to EPD,
just press Enter.
"""
    username = raw_input('Email (or username): ').strip()
    if not username:
        return None, None
    return username, getpass('Password: ')


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

# When use_webservice is True, one can control the webservice entry point enpkg
# will talk to. If not specified, a default will be used. Mostly useful for
# testing
#webservice_entry_point = "https://acme.com/api/{PLATFORM}/"

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
"""


def write(username=None, password=None, proxy=None):
    """
    Write the config file.
    """
    # If user is 'root', then always create the config file in sys.prefix,
    # otherwise in the user's HOME directory.
    if sys.platform != 'win32' and os.getuid() == 0:
        path = system_config_path
    else:
        path = home_config_path

    if username is None and password is None:
        username, password = input_auth()
    if username and password:
        if keyring:
            keyring.set_password(KEYRING_SERVICE_NAME, username, password)
            authline = 'EPD_username = %r' % username
        else:
            auth = ('%s:%s' % (username, password)).encode('base64')
            authline = 'EPD_auth = %r' % auth.strip()
        auth_section = """
# EPD subscriber authentication is required to access the EPD
# repository.  To change your credentials, use the 'enpkg --userpass'
# command, which will ask you for your email address (or username) and
# password.
%s
""" % authline
    else:
        auth_section = ''

    py_ver = PY_VER
    sys_prefix = sys.prefix
    version = __version__

    if proxy:
        proxy_line = 'proxy = %r' % proxy
    else:
        proxy_line = ('#proxy = <proxy string>  '
                      '# e.g. "http://<user>:<passwd>@123.0.1.2:8080"')

    fo = open(path, 'w')
    fo.write(RC_TMPL % locals())
    fo.close()
    print "Wrote configuration file:", path
    clear_cache()


def get_auth():
    """
    Retrieve the saved `auth` (username, password) tuple.
    """
    return AuthenticatorStore().load_auth()


def web_auth(auth,
        api_url='https://api.enthought.com/accounts/user/info/'):
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
    Extract the level of EPD subscription from the dictionary (`user`)
    returned by the web API.
    """
    if 'has_subscription' in user:
        if user.get('is_authenticated', False) and user.get('has_subscription', False):
            return 'EPD Basic or above'
        elif user.get('is_authenticated', False) and not(user.get('has_subscription', False)):
            return 'EPD Free'
        else:
            return None
    else:  # don't know the subscription level
        if user.get('is_authenticated', False):
            return 'EPD'
        else:
            return None


def subscription_message(user):
    """
    Return a 'subscription level' message based on the `user`
    dictionary.

    `user` is a dictionary, probably retrieved from the web API, that
    may contain `is_authenticated`, and `has_subscription`.
    """
    message = ""

    if user.get('is_authenticated', False):
        username, password = get_auth()
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


def authenticate(auth, remote=None):
    """
    Attempt to authenticate the user's credentials by the appropriate
    means.

    `auth` is a tuple of (username, password).
    `remote` is enpkg.remote, required if not using the web API to authenticate

    If 'use_webservice' is set, authenticate with the web API and return
    a dictionary containing user info on success.

    Else, authenticate with remote.connect and return a dict containing
    is_authenticated=True on success.

    If authentication fails, raise an exception.
    """
    user = {}
    if get('use_webservice'):
        # check credentials using web API
        try:
            user = web_auth(auth)
            assert user['is_authenticated']
        except Exception as e:
            raise AuthFailedError('Authentication failed: %s.' % e)
    else:
        # check credentials using remote.connect
        try:
            print 'Verifying user login...'
            remote.connect(auth)
            user = dict(is_authenticated=True)
        except KeyError:
            raise AuthFailedError('Authentication failed:'
                    ' Invalid user login.')
        except Exception as e:
            raise AuthFailedError('Authentication failed: %s.' % e)
    return user


def clear_auth():
    username = get('EPD_username')
    if username and keyring:
        keyring.set_password(KEYRING_SERVICE_NAME, username, '')
    change_auth('', None)


def change_auth(username, password):
    pat = re.compile(r'^(EPD_auth|EPD_username)\s*=.*$', re.M)

    # clear the cache so the next get_auth is correct
    clear_cache()

    path = get_path()
    if path is None:
        write(username, password)
        return

    if username is None and password is None:
        return

    with open(path) as fi:
        data = fi.read()

    if username == '':
        data = pat.sub('', data)
        with open(path, 'w') as fo:
            fo.write(data)
        return
    else:
        if not password:
            raise ValueError("No password -- this is a bug.")

        if keyring:
            keyring.set_password(KEYRING_SERVICE_NAME, username, password)
            authline = 'EPD_username = %r' % username
        else:
            auth = ('%s:%s' % (username, password)).encode('base64')
            authline = 'EPD_auth = %r' % auth.strip()

        if pat.search(data):
            data = pat.sub(authline, data)
        else:
            lines = data.splitlines()
            lines.insert(10, authline)
            data = '\n'.join(lines) + '\n'

        with open(path, 'w') as fo:
            fo.write(data)

def checked_change_auth(username, password, remote=None):
    """
    Only run change_auth if the credentials are authenticated (or if the
    username is None).  Print out subscription info if successful.

    `remote` is enpkg.remote and is required if not using the web API to
    authenticate.

    If successful at authenticating, return a dictionary containing user info.
    """
    auth = (username, password)
    user = {}

    # For backwards compatibility
    if username is None or username is '':
        change_auth(username, password)
        return user

    try:
        user = authenticate(auth, remote)
    except Exception as e:
        print e.message
        print "No credentials saved."
    else:
        change_auth(username, password)
        print subscription_message(user)
    return user


def prepend_url(url):
    f = open(get_path(), 'r+')
    data = f.read()
    pat = re.compile(r'^IndexedRepos\s*=\s*\[\s*$', re.M)
    if not pat.search(data):
        sys.exit("Error: IndexedRepos section not found")
    data = pat.sub(r"IndexedRepos = [\n  '%s'," % url, data)
    f.seek(0)
    f.write(data)
    f.close()


def clear_cache():
    if hasattr(read, 'cache'):
        del read.cache


def read():
    """
    Return the configuration from the config file as a dictionary,
    fix some values, and give defaults.
    """
    if hasattr(read, 'cache'):
        return read.cache

    path = get_path()
    if path is None:
        read.cache = Configuration()
        return read.cache
    else:
        config = Configuration()
        parser = PythonConfigurationParser()
        with open(path, "rt") as fp:
            data = fp.read()
        config.update(parser.parse(data))
        read.cache = config
        return read.cache

def get_repository_cache(prefix):
    return get("repository_cache")

def get(key, default=None):
    return read().get(key, default)


def print_config(remote, prefix):
    print "Python version:", PY_VER
    print "enstaller version:", __version__
    print "sys.prefix:", sys.prefix
    print "platform:", platform.platform()
    print "architecture:", platform.architecture()[0]
    print "use_webservice:", get('use_webservice')
    print "config file:", get_path()
    print "settings:"
    print "    prefix = %s" % prefix
    for k in 'local', 'noapp', 'proxy':
        print "    %s = %r" % (k, get(k))
    print "    IndexedRepos:", '(not used)' if get('use_webservice') else ''
    for repo in get('IndexedRepos'):
        print '        %r' % repo

    username, password = get_auth()
    user = {}
    try:
        user = authenticate((username, password), remote)
    except Exception as e:
        print e
    print subscription_message(user)

def is_auth_configured():
    """
    Returns True if enstaller configuration file has authentication
    information.

    Note
    ----
    This only checks whether the auth is configured, not whether the
    authentication information is correct.
    """
    # FIXME: this does not really belong here, and should be put in the
    # configuration object once it is not a module-level global
    auth = get("EPD_auth")
    if auth:
        return True
    else:
        return get("EPD_username") and keyring

class AuthenticatorStore(object):
    def __init__(self):
        self._auth = None

    def load_auth(self):
        """
        Load authentication information from enstaller configuration file (and
        potentially keyring).
        """
        if self._auth is None:
            self._auth = self._get_auth()
        return self._auth

    def _get_auth(self):
        old_auth = get("EPD_auth")
        if old_auth:
            decoded_auth = old_auth.decode('base64')
            parts = decoded_auth.split(":")
            if len(parts) != 2:
                raise InvalidConfiguration("Authentication string is corrupted")
            else:
                return tuple(parts)

        username = get("EPD_username")
        if username:
            password = None
            if keyring:
                password = keyring.get_password(KEYRING_SERVICE_NAME, username)
            if password:
                return username, password
            else:
                return None, None
        else:
            return None, None
