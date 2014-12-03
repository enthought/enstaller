import mock

from egginst.progress import console_progress_manager_factory
from egginst.console.simple import AFTER_BAR, BEFORE_BAR
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
        with mock.patch("egginst.console.simple.get_terminal_size",
                        return_value=(terminal_size, 25)):
            with mock.patch("sys.stdout") as mocked_stdout:
                progress = console_progress_manager_factory(message,
                                                            filename, size,
                                                            show_speed=True)

                with progress:
                    for _ in range(int(size / 1024)):
                        progress.update(1024)

        # Then
        for i, (args, kw) in enumerate(mocked_stdout.write.call_args_list):
            line = args[0].rstrip(AFTER_BAR).lstrip(BEFORE_BAR)
            self.assertTrue(len(line) < terminal_size)
