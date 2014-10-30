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
        from unittest2 import TestCase, skipIf
    else:
        from unittest import TestCase, skipIf
    TestCase.assertNotRegex = TestCase.assertNotRegexpMatches
    TestCase.assertRegex = TestCase.assertRegexpMatches

    import urlparse
    from urllib import pathname2url, unquote, url2pathname
    from urllib2 import splitpasswd, splitport, splituser

    import cPickle as pickle
    buffer = buffer
else:
    import configparser
    import http.client as http_client
    from io import StringIO, BytesIO

    from unittest import TestCase, skipIf
    TestCase.assertItemsEqual = TestCase.assertCountEqual

    NativeStringIO = StringIO

    text_type = str
    string_types = (str, )

    from urllib import parse as urlparse
    from urllib.parse import unquote
    from urllib.request import pathname2url, url2pathname
    from urllib.parse import splitpasswd, splitport, splituser

    import builtins
    import pickle
    buffer = memoryview

def input(prompt):
    # XXX: is defined as a function so that mock.patch can patch it without
    # trouble.
    if PY2:
        return raw_input(prompt)
    else:
        return builtins.input(prompt)

# Code taken from Jinja2
def with_metaclass(meta, *bases):
    # This requires a bit of explanation: the basic idea is to make a
    # dummy metaclass for one level of class instanciation that replaces
    # itself with the actual metaclass.  Because of internal type checks
    # we also need to make sure that we downgrade the custom metaclass
    # for one level to something closer to type (that's why __call__ and
    # __init__ comes back from type etc.).
    #
    # This has the advantage over six.with_metaclass in that it does not
    # introduce dummy classes into the final MRO.
    class metaclass(meta):
        __call__ = type.__call__
        __init__ = type.__init__
        def __new__(cls, name, this_bases, d):
            if this_bases is None:
                return type.__new__(cls, name, (), d)
            return meta(name, bases, d)
    return metaclass('temporary_class', None, {})
