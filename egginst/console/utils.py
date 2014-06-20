from ._compat import (text_type, string_types, PY2, auto_wrap_for_ansi,
                      strip_ansi, isatty, _default_text_stdout, is_bytes)

if not PY2:
    from ._compat import _find_binary_writer


echo_native_types = string_types + (bytes, bytearray)

def echo(message=None, file=None, nl=True):
    """Prints a message plus a newline to the given file or stdout.  On
    first sight, this looks like the print function, but it has improved
    support for handling Unicode and binary data that does not fail no
    matter how badly configured the system is.

    Primarily it means that you can print binary data as well as Unicode
    data on both 2.x and 3.x to the given file in the most appropriate way
    possible.  This is a very carefree function as in that it will try its
    best to not fail.

    In addition to that, if `colorama`_ is installed, the echo function will
    also support clever handling of ANSI codes.  Essentially it will then
    do the following:

    -   add transparent handling of ANSI color codes on Windows.
    -   hide ANSI codes automatically if the destination file is not a
        terminal.

    .. _colorama: http://pypi.python.org/pypi/colorama

    .. versionchanged:: 2.0
       Starting with version 2.0 of click, the echo function will work
       with colorama if it's installed.

    :param message: the message to print
    :param file: the file to write to (defaults to ``stdout``)
    :param nl: if set to `True` (the default) a newline is printed afterwards.
    """
    if file is None:
        file = _default_text_stdout()

    # Convert non bytes/text into the native string type.
    if message is not None and not isinstance(message, echo_native_types):
        message = text_type(message)

    # If there is a message, and we're in Python 3, and the value looks
    # like bytes, we manually need to find the binary stream and write the
    # message in there.  This is done separately so that most stream
    # types will work as you would expect.  Eg: you can write to StringIO
    # for other cases.
    if message and not PY2 and is_bytes(message):
        binary_file = _find_binary_writer(file)
        if binary_file is not None:
            file.flush()
            binary_file.write(message)
            if nl:
                binary_file.write(b'\n')
            binary_file.flush()
            return

    # ANSI-style support.  If there is no message or we are dealing with
    # bytes nothing is happening.  If we are connected to a file we want
    # to strip colors.  If we have support for wrapping streams (windows
    # through colorama) we want to do that.
    if message and not is_bytes(message):
        if not isatty(file):
            message = strip_ansi(message)
        elif auto_wrap_for_ansi is not None:
            file = auto_wrap_for_ansi(file)

    if message:
        file.write(message)
    if nl:
        file.write('\n')
    file.flush()
