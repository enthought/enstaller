import os
import struct
import sys


_DEFAULT_COLUMNS = 80
_DEFAULT_LINES = 25


def _posix_get_terminal_size():
    def ioctl_gwinsz(fd):
        try:
            import fcntl
            import termios
            cr = struct.unpack(
                'hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
        except Exception:
            return
        return cr

    cr = ioctl_gwinsz(0) or ioctl_gwinsz(1) or ioctl_gwinsz(2)
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            try:
                cr = ioctl_gwinsz(fd)
            finally:
                os.close(fd)
        except Exception:
            pass
    if not cr or not cr[0] or not cr[1]:
        cr = (os.environ.get('LINES', _DEFAULT_LINES),
              os.environ.get('COLUMNS', _DEFAULT_COLUMNS))
    return int(cr[1]), int(cr[0])


def _win32_get_terminal_size():
    from ._termui_win32 import get_terminal_size
    try:
        return get_terminal_size()
    except WindowsError:
        # FIXME: this typically happens when the stdout handle is not attached
        # to the console output. I don't know how to get the actual size in
        # this case
        return (_DEFAULT_COLUMNS, _DEFAULT_LINES)


def get_terminal_size():
    """Returns the current size of the terminal as tuple in the form
    ``(width, height)`` in columns and rows.
    """
    # If shutil has get_terminal_size() (Python 3.3 and later) use that
    if sys.version_info >= (3, 3):
        import shutil
        shutil_get_terminal_size = getattr(shutil, 'get_terminal_size', None)
        if shutil_get_terminal_size:
            sz = shutil_get_terminal_size()
            return sz.columns, sz.lines

    # columns, lines are the working values
    try:
        columns = int(os.environ['COLUMNS'])
    except (KeyError, ValueError):
        columns = 0

    try:
        lines = int(os.environ['LINES'])
    except (KeyError, ValueError):
        lines = 0

    if columns <= 0 or lines <= 0:
        if os.name == "nt":
            return _win32_get_terminal_size()
        else:
            return _posix_get_terminal_size()

    return columns, lines
