"""Error handling."""

from wsgilib import Error

from hisecon.config import LOGGER


__all__ = ['error']


def error(message: str, *, status: int = 400) -> Error:
    """Logs an error message and returns an Error."""

    LOGGER.error(message)
    return Error(message, status=status)
