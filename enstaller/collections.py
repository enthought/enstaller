from __future__ import absolute_import

import copy

from collections import Callable

from enstaller.compat import OrderedDict


class DefaultOrderedDict(OrderedDict):
    def __init__(self, default_factory, *a, **kw):
        OrderedDict.__init__(self, *a, **kw)
        self.default_factory = default_factory

    def __getitem__(self, key):
        try:
            return OrderedDict.__getitem__(self, key)
        except KeyError:
            return self.__missing__(key)

    def __missing__(self, key):
        self[key] = value = self.default_factory()
        return value

    def __reduce__(self):
        return (type(self), (self.default_factory(),), None, None,
                iter(self.items()))

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return type(self)(self.default_factory, self)

    def __deepcopy__(self, memo):
        return type(self)(self.default_factory,
                          (copy.deepcopy(item) for item in self.items()))

    def __repr__(self):
        return 'DefaultOrderedDict(%s, %s)' % (self.default_factory,
                                               OrderedDict.__repr__(self))
