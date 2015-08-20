"""Simple script to bootstrap enstaller into an existing python.

Example::

    # Fetch the latest released enstaller
    python bootstrap.py

one can also force a specific version of enstaller from a local egg built
through bdist_egg::

    python bootstrap.py egg_path

It only assumes python >= 2.6 or python >= 3.3, nothing else, not even
setuptools. In particular, it can be used to install eggs directly in our
masters.
"""
# !!! THIS SCRIPT SHOULD NOT IMPORT ANYTHING FROM EGGINST OR ENSTALLER !!!

import contextlib
import hashlib
import logging
import optparse
import os.path
import platform
import re
import subprocess
import sys

from distutils import log


DEFAULT_URL = "https://s3.amazonaws.com/enstaller-assets/enstaller/"
PYTHON_VERSION = ".".join(str(i) for i in sys.version_info[:2])

VERSION_RE = re.compile(r'''
    ^
    (?P<version>\d+\.\d+)          # minimum 'N.N'
    (?P<extraversion>(?:\.\d+)*)   # any number of extra '.N' segments
    ''', re.VERBOSE)

# We use a list of pairs instead of dict to keep order (we can't use
# OrderedDict to stay compatible with 2.6)
# We put dev versions at the end.
VERSION_TO_SHA256 = [
    ("4.8.7-1",
        "fb43035d456b7106e671069d35ced3db74b96b2b66ca7331420e1893fc2fb393"),
    ("4.8.6-1",
        "dd13c551cfa8a053aac692fb8c22cd3876737ea18d8e421a1376be06a0cab304"),
    ("4.8.5-1",
        "a2257be5d52416f2c516e00549f4053f9b017807bda0b87941fb966ef27b9558"),
    ("4.8.4-1",
        "f2007fb0a89e9538762ae432ed75a42667a4df53f79a728d6c045fc00a9949ee"),
    ("4.8.3-1",
        "505aed7957cd99d0d6169f446b179fb4d01fe4e9b87a8d83fa49c3c7bd79303b"),
    ("4.8.2-1",
        "21425a87b08fd166fa05e28cbd9f2c537e002df3e75c262fc68300f91b18df58"),
    ("4.8.1-1",
        "328faaf29e17cd23ffc496d35cc35234e8636faa08ebba31a8aa3cb6647ec2cc"),
    ("4.8.0-1",
        "034ab05208d93f490c35358eb03d826c06ed64c47617281875f7a8850e094132"),
    ("4.7.6-1",
        "f438269a02880e270425f573a22e205c6732e03b8450d316f9f3747bd5859faa"),
    ("4.6.5-1",
        "e2d578ba4fd337392324e2cb087c296275a36c83a11805342784bb9d7c3908eb"),
    ("4.6.2-1",
        "3a50e1a96a13bef6b6d5e02486882004cbaa90377b87580b159cc3e88c75f8f3"),
    ("4.5.6-1",
        "91d3dafa905587ce08d4a3e61870b121f370d19ff56c5f341f0c8c5cd84c6e2c"),
    ("4.5.3-1",
        "f72153411e273cfbbde039a0afdd41c773a443cd2f810231d7861869f8a9cf85"),
    ("4.8.0b1-1",
        "68b19ba3f70533435fcc0b00628629aff184711f826845f4090e8f793be79d68"),
    ("4.8.0.dev2961-1",
        "04ae47e79862c0198823440e3de71cdb857cc7135d5ec60286bd9308c92f0698"),
    ("4.8.0.dev2949-1",
        "bc86ac6a276a477d79d3afe379f57e05c70d32162af2f9030cb050352d7d3cc5"),
    ("4.8.0.dev3030-1",
        "be9d54a00f761891e55bf9d31ddbfb78296a77d1ac4159d2016ff1e1fbc7e3e2"),
    ("4.8.7.dev3189-1",
        "28156f4916bccf6f19d1b696fa3d349c58397ff6969de8c4811d56d839e9229b"),
]
VERSION_TO_SHA256_KEYS = [_[0] for _ in VERSION_TO_SHA256]


DEFAULT_VERSION = VERSION_TO_SHA256[0][0]
DEV_VERSION = "4.9.0.dev3250-1"


###################################
# Copied verbatim from ez_setup.py
###################################


def _clean_check(cmd, target):
    """
    Run the command to download target. If the command fails, clean up before
    re-raising the error.
    """
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        if os.access(target, os.F_OK):
            os.unlink(target)
        raise


def download_file_powershell(url, target):
    """
    Download the file at url to target using Powershell (which will validate
    trust). Raise an exception if the command cannot complete.
    """
    target = os.path.abspath(target)
    cmd = [
        'powershell',
        '-Command',
        "(new-object System.Net.WebClient).DownloadFile(%r, %r)"
        % (url, target),
    ]
    _clean_check(cmd, target)


def has_powershell():
    if platform.system() != 'Windows':
        return False
    cmd = ['powershell', '-Command', 'echo test']
    devnull = open(os.path.devnull, 'wb')
    try:
        try:
            subprocess.check_call(cmd, stdout=devnull, stderr=devnull)
        except:
            return False
    finally:
        devnull.close()
    return True


download_file_powershell.viable = has_powershell


def download_file_curl(url, target):
    cmd = ['curl', url, '--silent', '--output', target]
    _clean_check(cmd, target)


def has_curl():
    cmd = ['curl', '--version']
    devnull = open(os.path.devnull, 'wb')
    try:
        try:
            subprocess.check_call(cmd, stdout=devnull, stderr=devnull)
        except:
            return False
    finally:
        devnull.close()
    return True


download_file_curl.viable = has_curl


def download_file_wget(url, target):
    cmd = ['wget', url, '--quiet', '--output-document', target]
    _clean_check(cmd, target)


def has_wget():
    cmd = ['wget', '--version']
    devnull = open(os.path.devnull, 'wb')
    try:
        try:
            subprocess.check_call(cmd, stdout=devnull, stderr=devnull)
        except:
            return False
    finally:
        devnull.close()
    return True


download_file_wget.viable = has_wget


def download_file_insecure(url, target):
    """
    Use Python to download the file, even though it cannot authenticate the
    connection.
    """
    try:
        from urllib.request import urlopen
    except ImportError:
        from urllib2 import urlopen
    src = dst = None
    try:
        src = urlopen(url)
        # Read/write all in one block, so we don't create a corrupt file
        # if the download is interrupted.
        data = src.read()
        dst = open(target, "wb")
        dst.write(data)
    finally:
        if src:
            src.close()
        if dst:
            dst.close()


download_file_insecure.viable = lambda: True


def get_best_downloader():
    downloaders = [
        download_file_powershell,
        download_file_curl,
        download_file_wget,
        download_file_insecure,
    ]

    for dl in downloaders:
        if dl.viable():
            return dl

##############################################
# End of code copied verbatim from ez_setup.py
##############################################


def sha256(path):
    with open(path, "rb") as fp:
        m = hashlib.sha256()
        while True:
            chunk = fp.read(2 ** 16)
            if not chunk:
                break
            m.update(chunk)
    return m.hexdigest()


def download_enstaller(version=DEFAULT_VERSION, download_base=DEFAULT_URL,
                       to_dir=os.curdir, delay=15,
                       downloader_factory=get_best_downloader):
    """Download enstaller egg from a specified location and return its filename

    Parameters
    ----------
    version : str
        The version to fetch.
    """
    expected_sha256 = None
    for k, v in VERSION_TO_SHA256:
        if k == version:
            expected_sha256 = v
            break
    if expected_sha256 is None:
        msg = "Version {0!r} for is not known, aborting...".format(version)
        raise ValueError(msg)

    # making sure we use the absolute path
    to_dir = os.path.abspath(to_dir)
    egg_name = "enstaller-%s.egg" % (version, )
    url = download_base + egg_name
    saveto = os.path.join(to_dir, egg_name)
    if not os.path.exists(saveto):  # Avoid repeated downloads
        log.warn("Downloading %s", url)
        downloader = downloader_factory()
        downloader(url, saveto)
        if not sha256(saveto) == expected_sha256:
            os.unlink(saveto)
            raise ValueError("Checksum mismatch, aborting...")
    return os.path.realpath(saveto)


@contextlib.contextmanager
def disable_egginst_logging():
    logger = logging.getLogger("egginst")

    old = logger.propagate
    logger.propagate = False
    try:
        yield
    finally:
        logger.propagate = old


def bootstrap_enstaller(egg, version=DEFAULT_VERSION):
    sys.path.insert(0, egg)
    import egginst.main

    m = VERSION_RE.match(version)
    if m is not None:
        d = m.groupdict()
        main_version = d["version"]
        major, minor = [int(i) for i in main_version.split(".")]

        if (major, minor) < (4, 8) and hasattr(egginst.main, "object_code"):
            # HACK: avoiding error warning for old versions of enstaller when
            # trying to replace PLACEHOLDER hack in tests data. enstaller does
            # not have C code, so we don't need any replacement
            egginst.main.object_code.apply_placeholder_hack = \
                lambda *a, **kw: None

    # HACK: we patch argv to handle old enstallers whose main functions did not
    # take an argument
    with disable_egginst_logging():
        sys.argv[1:] = ["--remove", egg]
        egginst.main.main()

    sys.argv[1:] = [egg]
    egginst.main.main()


def cli_main(argv=None):
    argv = argv or sys.argv[1:]

    p = optparse.OptionParser(description="Simple script to bootstrap "
                                          "enstaller into a master.")
    p.add_option("--dev", action="store_true",
                 help="If specified, will get a development egg instead of "
                      "latest. Use at your own risk.")
    p.add_option("--version",
                 help="If specified, use this specific version instead of "
                      "latest release.")
    p.add_option("-l", "--list", action="store_true", dest="list_available",
                 help="If specified, list the available versions instead of "
                      "installing anything.")

    (options, args) = p.parse_args(argv)

    if options.list_available:
        for version in VERSION_TO_SHA256_KEYS:
            print(version)
        sys.exit(0)

    if len(args) == 1:
        egg = args[0]
        if not os.path.exists(egg):
            raise ValueError("path {0!r} does not exist !".format(egg))
    elif len(args) > 1:
        p.error("Only accept up to one argument.")
    else:
        if options.version:
            version = options.version
            egg = download_enstaller(version)
        elif options.dev:
            version = DEV_VERSION
            egg = download_enstaller(version)
        else:
            egg = download_enstaller()

    bootstrap_enstaller(egg)


# Kept for backward compatibility with the custom_tools/boot-enst.py script in
# enicab. Don't remove this unless you know what you are doing.
def main(prefix=sys.prefix, hook=False, pkgs_dirs=None, verbose=False):
    # egginst.bootstrap.main is called in enicab as follows::
    #   <python> boot-enst.py <enstaller egg>
    # hence the actual egg is sys.argv[1]
    egg_path = sys.argv[1]

    print("Bootstrapping: {0}".format(egg_path))
    bootstrap_enstaller(egg_path)


if __name__ == "__main__":
    cli_main()
