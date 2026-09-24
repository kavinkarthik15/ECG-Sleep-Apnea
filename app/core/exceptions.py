class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ModelUnavailableError(AppError):
    def __init__(self, message: str = "The inference model is unavailable.") -> None:
        super().__init__("MODEL_UNAVAILABLE", message, 503)


class SignalRejectedError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 422)