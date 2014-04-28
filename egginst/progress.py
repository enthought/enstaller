import uuid

from egginst.utils import human_bytes


def encore_progress_manager_factory(event_manager, source, message, steps,
                                    operation_id=None):
    # Local import to avoid hard dependency on encore (this functionality is
    # only used within canopy)
    from encore.events.api import ProgressManager

    if operation_id is None:
        operation_id = uuid.uuid4()

    progress = ProgressManager(event_manager, source=source,
                               operation_id=operation_id, message=message,
                               steps=steps)
    return progress


def console_progress_manager_factory(message, filename, size):
    from egginst.console import ProgressManager
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
        return self

    def __exit__(self, *a, **kw):
        return self._progress.__exit__(*a, **kw)

    def update(self, nbytes):
        self._n += nbytes
        return self._progress(self._n)


class _DummyProgressManager(object):
    def __enter__(self):
        return self
    def __exit__(self, *a, **kw):
        pass
    def __call__(self, step=0):
        pass


def progress_manager_factory(message, filename, size, event_manager, source,
                             operation_id=None):
    """
    Create the appropriate progress manager given the arguments
    """
    # FIXME: this needs to go away once the progress manager/enstaller
    # integration is refactored and fixed in canopy
    if event_manager is None:
        if message == "super":
            return _DummyProgressManager()
        else:
            return console_progress_manager_factory(message, filename, size)
    else:
        return encore_progress_manager_factory(event_manager, source, message,
                                               size, operation_id)
