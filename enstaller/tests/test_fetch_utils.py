import unittest

from egginst._compat import BytesIO
from enstaller.fetch_utils import _DEFAULT_CHUNK_SIZE, StoreResponse


class TestStoreResponse(unittest.TestCase):
    def test_buffsize(self):
        # Given
        response = StoreResponse(BytesIO())

        # When/Then
        self.assertEqual(response.default_buffsize, _DEFAULT_CHUNK_SIZE)

        # Given
        response = StoreResponse(BytesIO(), 1)

        # When/Then
        self.assertEqual(response.default_buffsize, 1)

        # Given
        response = StoreResponse(BytesIO(), 2**24)

        # When/Then
        self.assertEqual(response.default_buffsize, _DEFAULT_CHUNK_SIZE)

    def test_full_read(self):
        # Given
        r_content = b"some data"
        fp = BytesIO(r_content)
        response = StoreResponse(fp)

        # When
        data = response.read()

        # Then
        self.assertEqual(data, r_content)
        self.assertTrue(response.closed)

    def test_chunk_read(self):
        # Given
        r_content = b"some data" * _DEFAULT_CHUNK_SIZE
        fp = BytesIO(r_content)
        response = StoreResponse(fp)

        # When
        out = BytesIO()
        for chunk in response.iter_content():
            out.write(chunk)

        # Then
        self.assertEqual(out.getvalue(), r_content)
        self.assertTrue(response.closed)
