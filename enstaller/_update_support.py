import logging
import os.path
import subprocess
import sys
import zipfile

from egginst.main import BOOTSTRAP_ARCNAME

from enstaller.fetch import _DownloadManager


logger = logging.getLogger(__name__)

# Default bootstrap code used for older versions of enstaller. Starting from
# 4.8.0, enstaller eggs (as produced by bdist_egg) will contain a
# version-specific bootstrap code for more reliability.
_DEFAULT_BOOTSTRAP_CODE = """\
import contextlib
import logging
import re
import sys


VERSION_RE = re.compile(r'''
    ^
    (?P<version>\d+\.\d+)          # minimum 'N.N'
    (?P<extraversion>(?:\.\d+)*)   # any number of extra '.N' segments
    ''', re.VERBOSE)


@contextlib.contextmanager
def disable_egginst_logging():
    logger = logging.getLogger("egginst")

    old = logger.propagate
    logger.propagate = False
    try:
        yield
    finally:
        logger.propagate = old

egg = sys.argv[1]

sys.path.insert(0, egg)
import egginst.main

# HACK: we patch argv to handle old enstallers whose main functions did not
# take an argument
with disable_egginst_logging():
    sys.argv[1:] = ["--remove", egg]
    egginst.main.main()

sys.argv[1:] = [egg]
egginst.main.main()
"""


def inplace_update(session, repository, latest):
    downloader = _DownloadManager(session, repository)
    downloader.fetch(latest.key)

    target = downloader._path(latest.key)

    with zipfile.ZipFile(target) as zp:
        try:
            bootstrap_code = zp.read(BOOTSTRAP_ARCNAME)
            logger.debug("Using bootstrap code from egg")
        except KeyError:
            logger.debug("Using default bootstrap code")
            bootstrap_code = _DEFAULT_BOOTSTRAP_CODE

    d = os.path.dirname(target)

    script_path = os.path.join(d, "bootstrap.py")
    with open(script_path, "wt") as fp:
        fp.write(bootstrap_code)

    cmd = [sys.executable, script_path, target]
    ret = subprocess.call(cmd)
    if ret != 0:
        raise ValueError("Failed to run upgrade/bootstrap code.")
