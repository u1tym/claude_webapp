from __future__ import annotations


class NotFoundError(Exception):
    pass


class DuplicateError(Exception):
    pass


class InvalidInputError(Exception):
    pass


class CompletionNotAllowedError(Exception):
    pass
