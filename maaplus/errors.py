class MaaPlusError(Exception):
    """Base exception for MaaPlus."""


class RuntimeOperationError(MaaPlusError):
    """Raised when a MaaFramework-backed runtime operation fails."""


class LocatorNotFound(MaaPlusError):
    """Raised when a required locator does not match the current frame."""
