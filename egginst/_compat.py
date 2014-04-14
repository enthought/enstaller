"""
Simple py2/py3 shim
"""
import sys

PY2 = sys.version_info[0] == 2

if PY2:
    import ConfigParser as configparser
    import httplib as http_client
    from cStringIO import StringIO as BytesIO, StringIO

    NativeStringIO = BytesIO

    string_types = (str, unicode)
else:
    import configparser
    import http.client as http_client
    from io import StringIO, BytesIO

    NativeStringIO = StringIO

    string_types = (str, )
