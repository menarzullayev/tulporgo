"""Domain errors. `code` is stable (used by the bot for localized messages and by the API for error bodies)."""


class DomainError(Exception):
    status = 400

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


class NotFound(DomainError):
    status = 404


class Forbidden(DomainError):
    status = 403


class Conflict(DomainError):
    status = 409


class Invalid(DomainError):
    status = 422
