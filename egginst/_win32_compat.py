import ctypes
import os.path

from ctypes.wintypes import BOOL, DWORD, HANDLE, LPWSTR
from ctypes import POINTER, c_void_p


# CreateFile ctypes implementation from SO
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000

FILE_SHARE_DELETE = 0x00000004
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_READ_WRITE = (FILE_SHARE_READ | FILE_SHARE_WRITE)

OPEN_EXISTING = 3

IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003
REPARSE_MOUNTPOINT_HEADER_SIZE = 8

FSCTL_SET_REPARSE_POINT = 589988
FILE_FLAG_OPEN_REPARSE_POINT = 2097152
FILE_FLAG_BACKUP_SEMANTICS = 33554432
FILE_FLAG_REPARSE_BACKUP = 35651584  # FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS

INVALID_HANDLE_VALUE = -1
LPOVERLAPPED = c_void_p
LPSECURITY_ATTRIBUTES = c_void_p

NULL = 0
FALSE = BOOL(0)
TRUE = BOOL(1)


class _FileHandle(object):
    def __init__(self, handle):
        self._handle = handle

    def close(self):
        ctypes.windll.kernel32.CloseHandle(self._handle)


def CreateFile(filename, access, sharemode, attributes, creation, flags,
               template_file):
    # attributes and template_file ignored, kept for backward compat with
    # win32file
    return _FileHandle(HANDLE(ctypes.windll.kernel32.CreateFileW(
                       LPWSTR(filename),
                       DWORD(access),
                       DWORD(sharemode),
                       LPSECURITY_ATTRIBUTES(NULL),
                       DWORD(creation),
                       DWORD(flags),
                       HANDLE(NULL))))


class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", DWORD),
        ("dwHighDateTime", DWORD)
    ]


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", DWORD),
        ("ftCreationTime", FILETIME),
        ("ftLastAccessTime", FILETIME),
        ("ftLastWriteTime", FILETIME),
        ("dwVolumeSerialNumber", DWORD),
        ("nFileSizeHigh", DWORD),
        ("nFileSizeLow", DWORD),
        ("nNumberOfLinks", DWORD),
        ("nFileIndexHigh", DWORD),
        ("nFileIndexLow", DWORD)
    ]

# http://msdn.microsoft.com/en-us/library/windows/desktop/aa364952
GetFileInformationByHandle = ctypes.windll.kernel32.GetFileInformationByHandle
GetFileInformationByHandle.argtypes = [HANDLE, POINTER(BY_HANDLE_FILE_INFORMATION)]
GetFileInformationByHandle.restype = BOOL


# samefile code adapted from
# http://timgolden.me.uk/python/win32_how_do_i/see_if_two_files_are_the_same_file.html
def _get_read_handle(filename):
    if os.path.isdir(filename):
        dwFlagsAndAttributes = FILE_FLAG_BACKUP_SEMANTICS
    else:
        dwFlagsAndAttributes = 0
    return CreateFile(filename, GENERIC_READ, FILE_SHARE_READ, None,
                      OPEN_EXISTING, dwFlagsAndAttributes, None)


def _get_unique_id(hFile):
    file_info = BY_HANDLE_FILE_INFORMATION()
    res = GetFileInformationByHandle(hFile, ctypes.byref(file_info))
    if res == FALSE:
        raise RuntimeError("Call to GetFileInformationByHandle failed.")
    return (file_info.dwVolumeSerialNumber,
            file_info.nFileIndexHigh,
            file_info.nFileIndexLow)


def samefile(filename1, filename2):
    hFile1 = _get_read_handle(filename1)
    try:
        hFile2 = _get_read_handle(filename2)
        try:
            return _get_unique_id(hFile1._handle) == _get_unique_id(hFile2._handle)
        finally:
            hFile2.close()
    finally:
        hFile1.close()
