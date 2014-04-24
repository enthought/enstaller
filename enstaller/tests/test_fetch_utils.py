import unittest

from egginst._compat import BytesIO
from enstaller.fetch_utils import _DEFAULT_CHUNK_SIZE, StoreResponse


class TestStoreResponse(unittest.TestCase):
    def test_buffsize(self):
        # Given
        response = StoreResponse(BytesIO())

        # When/Then
        self.assertEqual(response.buffsize, _DEFAULT_CHUNK_SIZE)

        # Given
        response = StoreResponse(BytesIO(), 1)

        # When/Then
        self.assertEqual(response.buffsize, 1)

        # Given
        response = StoreResponse(BytesIO(), 2**24)

        # When/Then
        self.assertEqual(response.buffsize, _DEFAULT_CHUNK_SIZE)

