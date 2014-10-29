import os.path
import win32file


# samefile code taken from
# http://timgolden.me.uk/python/win32_how_do_i/see_if_two_files_are_the_same_file.html
def _get_read_handle(filename):
    if os.path.isdir(filename):
        dwFlagsAndAttributes = win32file.FILE_FLAG_BACKUP_SEMANTICS
    else:
        dwFlagsAndAttributes = 0
    return win32file.CreateFile(filename, win32file.GENERIC_READ,
                                win32file.FILE_SHARE_READ, None,
                                win32file.OPEN_EXISTING,
                                dwFlagsAndAttributes, None)


def _get_unique_id(hFile):
    _, _, _, _, volume, _, _, _, index_hi, index_lo = \
        win32file.GetFileInformationByHandle(hFile)
    return volume, index_hi, index_lo


def samefile(filename1, filename2):
    hFile1 = _get_read_handle(filename1)
    try:
        hFile2 = _get_read_handle(filename2)
        try:
            return _get_unique_id(hFile1) == _get_unique_id(hFile2)
        finally:
            hFile2.Close()
    finally:
        hFile1.Close()
