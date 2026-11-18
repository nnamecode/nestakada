class ManifestError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SourceReadError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class CoordinatorError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
