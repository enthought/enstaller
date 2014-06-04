from egginst.console import ProgressManager
from egginst.utils import human_bytes


def console_progress_manager_factory(message, filename, size):
    return ProgressManager(None, source=None, operation_id=None,
                           message=message, steps=size, progress_type=message,
                           filename=filename, disp_amount=human_bytes(size),
                           super_id=None)


class FileProgressManager(object):
    def __init__(self, progress_manager):
        self._progress = progress_manager
        self._n = 0

    def __enter__(self):
        self._n = 0
        return self._progress.__enter__()

    def __exit__(self, *a, **kw):
        return self._progress.__exit__(*a, **kw)

    def update(self, nbytes):
        self._n += nbytes
        return self._progress(self._n)
