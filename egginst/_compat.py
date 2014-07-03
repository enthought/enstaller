"""
Simple py2/py3 shim
"""
import logging
import sys

PY2 = sys.version_info[0] == 2

# For compatibility with 2.6
class NullHandler(logging.Handler):  # pragma: no cover
    def emit(self, record):
        pass

if PY2:
    import ConfigParser as configparser
    import httplib as http_client
    from cStringIO import StringIO as BytesIO, StringIO

    NativeStringIO = BytesIO

    text_type = unicode
    string_types = (str, unicode)

    if sys.version_info < (2, 7):
        from unittest2 import TestCase
    else:
        from unittest import TestCase
else:
    import configparser
    import http.client as http_client
    from io import StringIO, BytesIO

    from unittest import TestCase
    TestCase.assertItemsEqual = TestCase.assertCountEqual

    NativeStringIO = StringIO

    text_type = str
    string_types = (str, )
