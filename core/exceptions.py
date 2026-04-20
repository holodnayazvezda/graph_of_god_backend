class GraphOfGodBackendError(Exception):
    """Base backend error."""


class ConfigurationError(GraphOfGodBackendError):
    """Raised when backend configuration is invalid."""
