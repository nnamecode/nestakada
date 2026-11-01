from editor_runtime.guards import EditorFault


class SharedFault(EditorFault):
    def __init__(self, code, status=409, *, operation_not_started=False, operation_id=None, outcome_known=None):
        self.code, self.status = code, status
        self.operation_not_started = operation_not_started is True
        self.operation_id = operation_id
        self.outcome_known = outcome_known
        super().__init__()
