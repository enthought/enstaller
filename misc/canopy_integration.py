import uuid

from encore.events.api import ProgressManager


def encore_progress_manager_factory(event_manager, source, message, steps,
                                    operation_id=None):
    if operation_id is None:
        operation_id = uuid.uuid4()

    progress = ProgressManager(event_manager, source=source,
                               operation_id=operation_id, message=message,
                               steps=steps)
    return progress


def execute_actions(enpkg, actions, event_manager, execution_aborted):
    context = enpkg.execute_context(actions)
    for i, action in enumerate(context):
        for j, step in enumerate(action):
            action.progress_update(step)
            if execution_aborted.is_set():
                action.cancel()
        if action.is_canceled:
            return


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
