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


class IllegalPathError(GPConfigError):
    """Raised when a config path is malformed or escapes the cfg_folder."""

    def __init__(self, path: str, message: str = ""):
        self.path = path
        super().__init__(message or f"Illegal config path: {path}")


class ConfigReadonlyError(GPConfigError):
    """Raised when trying to modify or save a readonly config."""

    def __init__(self, config_name: str):
        super().__init__(f"Config '{config_name}' is readonly and cannot be modified")


class RegistrationError(GPConfigError):
    """Raised when there's an issue with class registration."""

    pass


class ConfigurableConstructionError(GPConfigError):
    """Raised when a construction hook returns an invalid object type.

    Attributes:
        path: Canonical dotted path used for object construction.
        expected_type: Registered configurable class that should be returned.
        actual_type: Type actually returned by the construction hook.
    """

    def __init__(
        self,
        path: str,
        expected_type: type,
        actual_type: type,
    ) -> None:
        """Initialize a construction contract error.

        Args:
            path: Canonical dotted path used for object construction.
            expected_type: Registered configurable class expected from the hook.
            actual_type: Type actually returned by the hook.
        """
        self.path = path
        self.expected_type = expected_type
        self.actual_type = actual_type
        super().__init__(
            f"Configurable '{expected_type.__name__}' from path '{path}' returned "
            f"{actual_type.__name__}; expected an instance of "
            f"{expected_type.__name__}"
        )


class ConfigValidationError(GPConfigError):
    """Raised when a config file fails validation."""

    def __init__(self, path: str, original_error: Exception):
        self.path = path
        self.original_error = original_error
        super().__init__(f"Validation failed for '{path}': {original_error}")
