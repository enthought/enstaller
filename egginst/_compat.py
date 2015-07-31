"""
Simple py2/py3 shim
"""
import logging


# For compatibility with 2.6
class NullHandler(logging.Handler):  # pragma: no cover
    def emit(self, record):
        pass

import egginst.vendor.six

egginst.vendor.six.add_move(egginst.vendor.six.MovedModule("unittest",
                                                           "unittest2",
                                                           "unittest"))

PY2 = egginst.vendor.six.PY2

if PY2:
    buffer = buffer
else:
    buffer = memoryview


def assertCountEqual(self, first, second, msg=None):
    if PY2:
        return self.assertItemsEqual(first, second, msg)
    else:
        return self.assertCountEqual(first, second, msg)


def input(prompt):
    # XXX: is defined as a function so that mock.patch can patch it without
    # trouble.
    if PY2:
        return raw_input(prompt)
    else:
        import builtins
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
