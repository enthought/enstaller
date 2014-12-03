import mock

from egginst.progress import console_progress_manager_factory
from egginst.vendor.six.moves import unittest


class TestProgressBar(unittest.TestCase):
    def test_dont_overflow(self):
        # Ensure we don't overflow the terminal size

        # Given
        message = "fetching"
        filename = "MKL-10.3.1-1.egg"
        size = 1024 ** 2 * 70
        terminal_size = 80

        # When
        with mock.patch("sys.stdout") as mocked_stdout:
            progress = console_progress_manager_factory("fetching",
                                                        filename, size,
                                                        show_speed=True)

            with progress:
                for _ in range(1000):
                    progress.update(1024 * 256)

        # Then
        for args, kw in mocked_stdout.write.call_args_list:
            line = len(args[0])
            self.assertTrue(line <= terminal_size)
