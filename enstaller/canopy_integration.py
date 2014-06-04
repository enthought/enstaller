def execute_actions(enpkg, actions, event_manager, execution_aborted):
    context = enpkg.execute_context(actions)
    for i, action in enumerate(context):
        for j, step in enumerate(action):
            action.progress_update(step)
            if execution_aborted.is_set():
                action.cancel()
        if action.is_canceled:
            return
