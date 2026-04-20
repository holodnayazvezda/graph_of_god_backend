from graph_of_god_backend.core.exceptions import GraphOfGodBackendError


class InvalidProfileReferenceError(GraphOfGodBackendError):
    """Raised when a VK profile link or handle cannot be parsed."""


class VKApiError(GraphOfGodBackendError):
    """Raised when VK API returns an error payload."""

    def __init__(self, message: str, *, error_code: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class VKResponseFormatError(GraphOfGodBackendError):
    """Raised when VK API returns an unexpected payload."""


class VKOAuthError(GraphOfGodBackendError):
    """Raised when VK OAuth returns an error payload."""
