import errno
import logging
import os
import re
import sys
import uuid


def win32_rename(src, dst):
    """A rename that does not fail if dst already exists.

    Note: It will still fail if dst is already opened,
    though.
    """
    try:
        os.rename(src, dst)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
        # FIXME: this could still fail if the file is already opened. That's
        # not something we need ATM, adding unlink with POSIX semantics can be
        # done later if needed (see e.g. hg rename).
        os.unlink(dst)
        os.rename(src, dst)


def rename(src, dst):
    """Atomic rename that works on windows."""
    if sys.platform == "win32":
        return win32_rename(src, dst)
    else:
        return os.rename(src, dst)


def safe_write(target, writer, mode="wt"):
    """a 'safe' way to write to files.

    Instead of writing directly into a file, this function writes to a
    temporary file, and then rename the file to the target if no error occured.
    On most platforms, rename is atomic, so this avoids leaving stale files in
    inconsistent states.

    Parameters
    ----------
    target: str
        destination to write to
    writer: callable or data
        if callable, assumed to be function which takes one argument, a file
        descriptor, and writes content to it. Otherwise, assumed to be data
        to be directly written to target.
    mode: str
        opening mode
    """
    if not callable(writer):
        data = writer
        writer = lambda fp: fp.write(data)

    tmp_target = "%s.tmp%s" % (target, uuid.uuid4().hex)
    f = open(tmp_target, mode)
    try:
        writer(f)
    finally:
        f.close()
    rename(tmp_target, target)


def pkg_config_dir(prefix):
    """Return the full path of the pkgconfig directory for the given prefix."""
    return os.path.join(prefix, "lib", "pkgconfig")


def update_pkg_config_prefix(pc_file, prefix):
    """Overwrite the prefix variable for the given .pc pkg-config file with the
    given prefix.

    The .pc file is written in-place
    """
    if not os.path.isabs(pc_file):
        pc_file = os.path.join(pkg_config_dir(prefix), pc_file)

    pat = re.compile(r"^prefix=(.*)$", re.M)
    if os.path.exists(pc_file):
        with open(pc_file) as fp:
            data = fp.read()
            data = pat.sub("prefix={0}".format(prefix), data)
        safe_write(pc_file, data, "wt")
    else:
        # FIXME: should this be an error ?
        logging.warn("%s not found" % pc_file)
