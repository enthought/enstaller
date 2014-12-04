# Code copied from colorama.win32. Original notice below
# Copyright Jonathan Hartley 2013. BSD 3-Clause license, see LICENSE file.

# from winbase.h
STDOUT = -11
STDERR = -12

try:
    import ctypes
    from ctypes import LibraryLoader
    windll = LibraryLoader(ctypes.WinDLL)
    from ctypes import wintypes
except (AttributeError, ImportError):
    windll = None
    SetConsoleTextAttribute = lambda *_: None
else:
    from ctypes import byref, Structure, POINTER

    class CONSOLE_SCREEN_BUFFER_INFO(Structure):
        """struct in wincon.h."""
        _fields_ = [
            ("dwSize", wintypes._COORD),
            ("dwCursorPosition", wintypes._COORD),
            ("wAttributes", wintypes.WORD),
            ("srWindow", wintypes.SMALL_RECT),
            ("dwMaximumWindowSize", wintypes._COORD),
        ]

        def __str__(self):
            return '(%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d)' % (
                self.dwSize.Y, self.dwSize.X,
                self.dwCursorPosition.Y, self.dwCursorPosition.X,
                self.wAttributes,
                self.srWindow.Top, self.srWindow.Left, self.srWindow.Bottom,
                self.srWindow.Right,
                self.dwMaximumWindowSize.Y, self.dwMaximumWindowSize.X
            )

    _GetStdHandle = windll.kernel32.GetStdHandle
    _GetStdHandle.argtypes = [
        wintypes.DWORD,
    ]
    _GetStdHandle.restype = wintypes.HANDLE

    _GetConsoleScreenBufferInfo = windll.kernel32.GetConsoleScreenBufferInfo
    _GetConsoleScreenBufferInfo.argtypes = [
        wintypes.HANDLE,
        POINTER(CONSOLE_SCREEN_BUFFER_INFO),
    ]
    _GetConsoleScreenBufferInfo.restype = wintypes.BOOL

    handles = {
        STDOUT: _GetStdHandle(STDOUT),
        STDERR: _GetStdHandle(STDERR),
    }

    def GetConsoleScreenBufferInfo(stream_id=STDOUT):
        handle = handles[stream_id]
        csbi = CONSOLE_SCREEN_BUFFER_INFO()
        _GetConsoleScreenBufferInfo(handle, byref(csbi))
        return csbi


def get_terminal_size():
    srWindow = GetConsoleScreenBufferInfo(STDOUT).srWindow
    columns = srWindow.Right - srWindow.Left + 1
    lines = srWindow.Bottom - srWindow.Top + 1
    return (columns, lines)
