# src/gpconfig/__init__.py
"""gpconfig - General Purpose Configuration management for Python."""

from gpconfig.config import GPConfig
from gpconfig.configurable import GPConfigurable
from gpconfig.manager import GPConfigManager, GPConfigFolder
from gpconfig.exceptions import (
    GPConfigError,
    ConfigFolderError,
    ConfigNotFoundError,
    ConfigReadonlyError,
    RegistrationError,
    ConfigValidationError,
)

__all__ = [
    # Core classes
    "GPConfig",
    "GPConfigurable",
    "GPConfigManager",
    "GPConfigFolder",
    # Exceptions
    "GPConfigError",
    "ConfigFolderError",
    "ConfigNotFoundError",
    "ConfigReadonlyError",
    "RegistrationError",
    "ConfigValidationError",
]

__version__ = "0.3.1"
