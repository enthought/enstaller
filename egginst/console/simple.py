import os
import struct
import sys
import time


if os.name == 'nt':
    BEFORE_BAR = '\r'
    AFTER_BAR = '\n'
else:
    BEFORE_BAR = '\r\033[?25l'
    AFTER_BAR = '\033[?25h\n'


class _DummyStream(object):
    def flush(self):
        pass

    def write(self, data):
        pass


class ExpAverager(object):
    def __init__(self, fill_size=3):
        self.fill_size = fill_size
        self._cur = None
        self.alpha = 0.9
        self._hit = 0

    @property
    def is_filled(self):
        return self._hit >= self.fill_size

    def append(self, value):
        if self._cur is None:
            self._cur = value
        else:
            self._cur = self.alpha * self._cur + (1 - self.alpha) * value

        self._hit += 1

    @property
    def value(self):
        return self._cur


def _human_speed(speed):
    if speed < 1.:
        return "-- b/sec"
    else:
        if speed > 1024 ** 2:
            speed = speed / 1024 ** 2
            unit = "Mb"
        elif speed > 1024:
            speed = speed / 1024
            unit = "kb"
        else:
            unit = "b"
        return "%.1f %s/sec" % (speed, unit)


class ProgressBar(object):
    def __init__(self, length=None, bar_template='%(bar)s', width=30,
                 fill_char='#', show_speed=False):
        if sys.stdout.isatty():
            self._stream = sys.stdout
        else:
            self._stream = _DummyStream()

        self._entered = False
        self._pos = 0
        self.fill_char = fill_char

        if length is not None:
            self._length = length
        else:
            raise ValueError("no length not supported yet.")

        self.width = width
        self.last_written_bar_pos = 0
        self.bar_template = bar_template

        self.show_speed = show_speed

        self._start = self._last_render = time.time()
        self._avg_speed = ExpAverager(5)
        self._elapsed = 0.

    def render_finish(self):
        self._stream.write(AFTER_BAR)
        self._stream.flush()

    @property
    def _elapsed_since_last_render(self):
        return time.time() - self._last_render

    @property
    def has_length(self):
        return self._length is not None

    @property
    def needs_render(self):
        # We force a render at least 4x / sec
        return (self.relative_bar_pos > self.last_written_bar_pos
                or self._elapsed_since_last_render >= 0.25) \
            and self.relative_bar_pos <= self.width

    @property
    def relative_bar_pos(self):
        assert self.has_length
        if self._length == 0:
            return 0
        else:
            return int(self._pos * 1. / self._length * self.width)

    @property
    def speed(self):
        if self._elapsed >= 0.1:
            return self._pos / self._elapsed
        else:
            return 0.

    def _update_time_state(self):
        now = time.time()
        self._last_render = now

        self._elapsed = now - self._start

        self._last_pos = self._pos
        self._last = now

    def update(self, n_steps):
        self._pos += n_steps

        if self.needs_render:
            self._update_time_state()

            if self.show_speed:
                speed = self.speed

                self._avg_speed.append(speed)
                if self._avg_speed.is_filled:
                    speed = self._avg_speed.value

                self.info = _human_speed(speed)
            else:
                self.info = ""

            self._render()

    def _render(self):
        self.last_written_bar_pos = self.relative_bar_pos
        bar_value = self.fill_char * self.relative_bar_pos + \
            " " * (self.width - self.relative_bar_pos)
        data = {
            "bar": bar_value,
            "info": self.info,
            "label": "",
        }
        rendered_bar = self.bar_template % data
        bar = BEFORE_BAR + rendered_bar
        self._stream.write(bar)
        self._stream.write(" " * (get_terminal_size()[0] - len(bar)))
        self._stream.flush()

    def __enter__(self):
        self._entered = True
        return self

    def __exit__(self, *a, **kw):
        self.render_finish()

    def __iter__(self):
        if not self._entered:
            msg = "You need to use progress bars in a `with` block."
            raise RuntimeError(msg)
        return self


def get_terminal_size():
    """Returns the current size of the terminal as tuple in the form
    ``(width, height)`` in columns and rows.
    """
    # If shutil has get_terminal_size() (Python 3.3 and later) use that
    if sys.version_info >= (3, 3):
        import shutil
        shutil_get_terminal_size = getattr(shutil, 'get_terminal_size', None)
        if shutil_get_terminal_size:
            sz = shutil_get_terminal_size()
            return sz.columns, sz.lines

    DEFAULT_COLUMNS = 80

    def ioctl_gwinsz(fd):
        try:
            import fcntl
            import termios
            cr = struct.unpack(
                'hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
        except Exception:
            return
        return cr

    cr = ioctl_gwinsz(0) or ioctl_gwinsz(1) or ioctl_gwinsz(2)
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            try:
                cr = ioctl_gwinsz(fd)
            finally:
                os.close(fd)
        except Exception:
            pass
    if not cr or not cr[0] or not cr[1]:
        cr = (os.environ.get('LINES', 25),
              os.environ.get('COLUMNS', DEFAULT_COLUMNS))
    return int(cr[1]), int(cr[0])
