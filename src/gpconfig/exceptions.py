"""Custom exceptions for gpconfig library."""


class GPConfigError(Exception):
    """Base exception for all gpconfig errors."""

    pass


class ConfigFolderError(GPConfigError):
    """Raised when the config folder cannot be found or is invalid."""

    pass


class ConfigNotFoundError(GPConfigError):
    """Raised when a requested config path doesn't exist."""

    def __init__(self, path: str, message: str = ""):
        self.path = path
        super().__init__(message or f"Config not found: {path}")


class ConfigReadonlyError(GPConfigError):
    """Raised when trying to modify or save a readonly config."""

    def __init__(self, config_name: str):
        super().__init__(f"Config '{config_name}' is readonly and cannot be modified")


class RegistrationError(GPConfigError):
    """Raised when there's an issue with class registration."""

    pass


class ConfigValidationError(GPConfigError):
    """Raised when a config file fails validation."""

    def __init__(self, path: str, original_error: Exception):
        self.path = path
        self.original_error = original_error
        super().__init__(f"Validation failed for '{path}': {original_error}")
