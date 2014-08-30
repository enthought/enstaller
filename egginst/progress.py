import sys

from egginst.console import ProgressBar
from egginst.utils import human_bytes


def dummy_progress_bar_factory(*a, **kw):
    return _DummyProgressBar()


def console_progress_manager_factory(message, filename, size, steps=None):
    if steps is None:
        steps = size
    first_line = "%-46s %20s" % (filename, '[%s]' % message)
    sys.stdout.write(first_line + "\n")

    left_align = 10
    # 2 for '[' and ']'
    width = len(first_line) - left_align - 2 - 1
    bar_template = "{0:>10}".format(human_bytes(size))
    bar_template += "%(label)s [%(bar)s] %(info)s"

    return ProgressBar(length=steps, bar_template=bar_template, width=width,
                       fill_char=".", show_percent=False, show_eta=False)


class _DummyProgressBar(object):
    def update(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a, **kw):
        pass
