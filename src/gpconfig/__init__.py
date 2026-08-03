# src/gpconfig/__init__.py
"""gpconfig - General Purpose Configuration management for Python."""

from gpconfig.config import GPConfig
from gpconfig.configurable import GPConfigurable, GPConfigurableContext
from gpconfig.manager import GPConfigManager, GPConfigFolder
from gpconfig.exceptions import (
    GPConfigError,
    ConfigFolderError,
    ConfigNotFoundError,
    IllegalPathError,
    ConfigReadonlyError,
    RegistrationError,
    ConfigValidationError,
    ConfigurableConstructionError,
)

__all__ = [
    # Core classes
    "GPConfig",
    "GPConfigurable",
    "GPConfigurableContext",
    "GPConfigManager",
    "GPConfigFolder",
    # Exceptions
    "GPConfigError",
    "ConfigFolderError",
    "ConfigNotFoundError",
    "IllegalPathError",
    "ConfigReadonlyError",
    "RegistrationError",
    "ConfigValidationError",
    "ConfigurableConstructionError",
]

__version__ = "0.3.5"
