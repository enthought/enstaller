from __future__ import print_function

from egginst._compat import PY2, input
from egginst.vendor.six.moves import urllib

import getpass
import json
import logging
import sys
import textwrap
import zlib

from os.path import abspath, expanduser, getmtime, getsize

from egginst.utils import compute_md5

from enstaller.errors import InvalidFormat
from enstaller.vendor import requests
from enstaller.versions.pep386_workaround import PEP386WorkaroundVersion
from enstaller import plat


_GZIP_MAGIC = "1f8b"

PY_VER = '%i.%i' % sys.version_info[:2]


def abs_expanduser(path):
    return abspath(expanduser(path))


def canonical(s):
    """
    return the canonical representations of a project name
    DON'T USE THIS IN NEW CODE (ONLY (STILL) HERE FOR HISTORICAL REASONS)
    """
    # eventually (once Python 2.6 repo eggs are no longer supported), this
    # function should only return s.lower()
    s = s.lower()
    s = s.replace('-', '_')
    if s == 'tables':
        s = 'pytables'
    return s


def comparable_version(version):
    """
    Given a version string (e.g. '1.3.0.dev234'), return an object which
    allows correct comparison.
    """
    return PEP386WorkaroundVersion.from_string(version)


def info_file(path):
    return dict(size=getsize(path),
                mtime=getmtime(path),
                md5=compute_md5(path))


def cleanup_url(url):
    """
    Ensure a given repo string, i.e. a string specifying a repository,
    is valid and return a cleaned up version of the string.
    """
    p = urllib.parse.urlparse(url)
    scheme, netloc, path, params, query, fragment = p[:6]

    if scheme == "":
        scheme = "file"

    if scheme == "file":
        netloc = expanduser(netloc)
        path = expanduser(path)

    if scheme in ('http', 'https', 'file'):
        if not path.endswith('/'):
            path += '/'
    else:
        raise InvalidFormat("Unsupported scheme: {0!r}".format(url))

    return urllib.parse.urlunparse((scheme, netloc, path, params, query, fragment))


def fill_url(url):
    url = url.replace('{ARCH}', plat.arch)
    url = url.replace('{SUBDIR}', plat.subdir)
    url = url.replace('{PLATFORM}', plat.custom_plat)
    return cleanup_url(url)


def path_to_uri(path):
    """Convert the given path string to a valid URI.

    It produces URI that are recognized by the windows
    shell API on windows, e.g. 'C:\\foo.txt' will be
    'file:///C:/foo.txt'"""
    return urllib.parse.urljoin("file:", urllib.request.pathname2url(path))


def uri_to_path(uri):
    """Convert a valid file uri scheme string to a native
    path.

    The returned path should be recognized by the OS and
    the native path functions, but is not guaranteed to use
    the native path separator (e.g. it could be C:/foo.txt
    on windows instead of C:\\foo.txt)."""
    urlpart = urllib.parse.urlparse(uri)
    if urlpart.scheme == "file":
        unquoted = urllib.parse.unquote(uri)
        path = unquoted[len("file://"):]
        if sys.platform == "win32" and path.startswith("/"):
            path = path[1:]
        return urllib.request.url2pathname(path)
    else:
        raise ValueError("Invalid file uri: {0}".format(uri))


def under_venv():
    return hasattr(sys, "real_prefix")


def real_prefix():
    if under_venv():
        return sys.real_prefix
    else:
        return sys.prefix


def prompt_yes_no(message, force_yes=False):
    """
    Prompt for a yes/no answer for the given message. Returns True if the
    answer is yes.

    Parameters
    ----------
    message : str
        The message to prompt the user with
    force_yes: boolean
        If True, then the message is only displayed, and the answer is assumed
        to be yes.

    """
    if force_yes:
        print(message)
        return True
    else:
        yn = input(message)
        return yn.lower() in set(['y', 'yes'])


def _bytes_to_hex(bdata):
    # Only use for tiny strings
    if PY2:
        return "".join("%02x" % (ord(c),) for c in bdata)
    else:
        return "".join("%02x" % c for c in bdata)


def decode_json_from_buffer(data):
    """
    Returns the decoded json dictionary contained in data. Optionally
    decompress the data if the buffer's data are detected as gzip-encoded.
    """
    if len(data) >= 2 and _bytes_to_hex(data[:2]) == _GZIP_MAGIC:
        # Some firewall/gateway has the "feature" of stripping Content-Encoding
        # from the response headers, without actually uncompressing the data,
        # in which case requests will give use a response object with
        # compressed data. We try to detect this case here, and decompress it
        # as requests would do if gzip format is detected.
        logging.debug("Detected compressed data with stripped header")
        try:
            data = zlib.decompress(data, 16 + zlib.MAX_WBITS)
        except (IOError, zlib.error) as e:
            # ContentDecodingError is the exception raised by requests when
            # urllib3 fails to decompress.
            raise requests.exceptions.ContentDecodingError(
                "Detected gzip-compressed response, but failed to decode it.",
                e)

    try:
        decoded_data = data.decode("utf8")
    except UnicodeDecodeError as e:
        raise ValueError("Invalid index data, try again ({0!r})".format(e))

    return json.loads(decoded_data)


def input_auth():
    """
    Prompt user for username and password.  Return (username, password)
    tuple or (None, None) if left blank.
    """
    print(textwrap.dedent("""\
        Please enter the email address and password for your Canopy / EPD
        subscription.  """))
    username = input('Email (or username): ').strip()
    if not username:
        return None, None
    return username, getpass.getpass('Password: ')
