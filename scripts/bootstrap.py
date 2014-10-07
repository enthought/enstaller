"""
Simple script to bootstrap enstaller into an existing python.

Usage::

    python bootstrap.py

It only assumes python >= 2.6 or python >= 3.3, nothing else, not even
setuptools.
"""
import contextlib
import logging
import optparse
import os.path
import platform
import subprocess
import sys

from distutils import log


DEFAULT_VERSION = "4.7.5"
DEFAULT_URL = "https://s3.amazonaws.com/archive.enthought.com/enstaller/"
PYTHON_VERSION = ".".join(str(i) for i in sys.version_info[:2])

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
        "(new-object System.Net.WebClient).DownloadFile(%(url)r, %(target)r)"
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


def download_enstaller(version=DEFAULT_VERSION, download_base=DEFAULT_URL,
                       to_dir=os.curdir, delay=15,
                       downloader_factory=get_best_downloader):
    """Download enstaller egg from a specified location and return its filename

    Parameters
    ----------
    version : str
        The version to fetch.
    """
    # making sure we use the absolute path
    to_dir = os.path.abspath(to_dir)
    egg_name = "enstaller-%s-py%s.egg" % (version, PYTHON_VERSION)
    url = download_base + egg_name
    saveto = os.path.join(to_dir, egg_name)
    if not os.path.exists(saveto):  # Avoid repeated downloads
        log.warn("Downloading %s", url)
        downloader = downloader_factory()
        downloader(url, saveto)
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

    if version in ("4.7.5",):
        # HACK: avoiding error warning for old versions of enstaller when
        # trying to replace PLACEHOLDER hack in tests data. enstaller does
        # not have C code, so we don't need any replacement
        egginst.main.object_code.apply_placeholder_hack = lambda *a, **kw: None

    with disable_egginst_logging():
        egginst.main.main(["--remove", egg])
    egginst.main.main([egg])


def main(argv=None):
    argv = argv or sys.argv[1:]

    p = optparse.OptionParser()

    (options, args) = p.parse_args(argv)
    if len(args) == 1:
        egg = args[0]
    elif len(args) > 1:
        p.error("Only accept up to one argument.")
    else:
        egg = download_enstaller()

    bootstrap_enstaller(egg)


if __name__ == "__main__":
    main()
