from __future__ import absolute_import

import copy
import unittest

from egginst.vendor.six.moves import cPickle
from ..collections import DefaultOrderedDict


class TestDefaultOrderedDict(unittest.TestCase):
    def test_simple(self):
        # Given
        data = DefaultOrderedDict(list)

        # When
        data[1].append(1)
        data[0].append(0)

        # Then
        self.assertEqual(list(data.keys()), [1, 0])
        self.assertEqual(data[0], [0])
        self.assertEqual(data[1], [1])
        self.assertEqual(data[2], [])
        r_repr = ("OrderedDefaultDict(<type 'list'>, "
                  "DefaultOrderedDict([(1, [1]), (0, [0]), (2, [])]))")
        self.assertEqual(repr(data), r_repr)

    def test_pickling(self):
        # Given
        data = DefaultOrderedDict(list)
        data[1].append(1)
        data[0].append(0)

        # When
        s = cPickle.dumps(data)
        unpickled_data = cPickle.loads(s)

        # Then
        self.assertEqual(unpickled_data, data)

    def test_copy(self):
        # Given
        data = DefaultOrderedDict(list)
        data[1].append(1)

        # When
        data_copy = data.copy()

        # Then
        self.assertEqual(data, data_copy)

        # When
        # Check we don't do deep copy
        data[1].append(2)

        # Then
        self.assertEqual(data, data_copy)

        # When
        data.pop(1)
        self.assertEqual(data_copy[1], [1, 2])

    def test_deepcopy(self):
        # Given
        data = DefaultOrderedDict(list)
        data[1].append(1)

        # When
        data_copy = copy.deepcopy(data)

        # Then
        self.assertEqual(data, data_copy)

        # When
        data[1].append(2)

        # Then
        self.assertNotEqual(data_copy[1], data[1])
