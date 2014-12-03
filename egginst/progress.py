import sys

from egginst.console import ProgressBar, get_terminal_size
from egginst.console.simple import _MAX_SPEED_LABEL_DISPLAY
from egginst.utils import human_bytes


def dummy_progress_bar_factory(*a, **kw):
    return _DummyProgressBar()


def _compute_optimal_first_line(message, filename):
    term_width = get_terminal_size()[0]
    # -------------------------------------------- term width
    # first_line_left first_line_right speed_label
    # The '1' are for spaces
    first_line_length = term_width - 1 - _MAX_SPEED_LABEL_DISPLAY
    first_line_right = 20
    first_line_left = first_line_length - first_line_right - 1

    first_line_template = "%%-%ss %%%ss" % (first_line_left, first_line_right)
    if len(filename) >= first_line_left:
        ellipsis = "... "
        display_filename = (filename[:first_line_left - len(ellipsis)] +
                            ellipsis)
    else:
        display_filename = filename

    first_line = first_line_template % (display_filename, '[%s]' % message)
    return first_line


def console_progress_manager_factory(message, filename, size, steps=None,
                                     show_speed=False):
    if steps is None:
        steps = size

    first_line = _compute_optimal_first_line(message, filename)
    sys.stdout.write(first_line + "\n")

    left_align = 10
    # 2 for '[' and ']'
    width = len(first_line) - left_align - 2 - 1
    bar_template = "{0:>10}".format(human_bytes(size))
    bar_template += "%(label)s [%(bar)s] %(info)s"

    return ProgressBar(length=steps, bar_template=bar_template, width=width,
                       fill_char=".", show_speed=show_speed)


class _DummyProgressBar(object):
    def update(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a, **kw):
        pass
