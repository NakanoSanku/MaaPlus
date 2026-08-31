class MaaPlusError(Exception):
    """Base exception for MaaPlus."""


class RuntimeOperationError(MaaPlusError):
    """Raised when a MaaFramework-backed runtime operation fails."""
