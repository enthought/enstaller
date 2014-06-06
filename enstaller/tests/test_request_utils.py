import sys

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

from enstaller.requests_utils import FileResponse


class TestFileResponse(unittest.TestCase):
    def test_simple(self):
        # Given
        path = __file__
        with open(path, "rb") as fp:
            r_data = fp.read()

        resp = FileResponse(path, "rb")

        # When
        data = resp.read()

        # Then
        self.assertEqual(data, r_data)

    def test_getheaders(self):
        # Given
        resp = FileResponse(__file__, "rb")

        # When
        header = resp.getheaders("dummy")

        # Then
        self.assertEqual(header, [])

    def test_release_conn(self):
        # Given
        resp = FileResponse(__file__, "rb")

        # When
        resp.release_conn()

        # Then
        self.assertTrue(resp.closed)
