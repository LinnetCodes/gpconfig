# Exceptions

gpconfig defines a set of custom exception classes for handling various error scenarios during configuration management.

## Import

```python
from gpconfig import (
    GPConfigError,
    ConfigFolderError,
    ConfigNotFoundError,
    ConfigReadonlyError,
    RegistrationError,
    ConfigValidationError,
)
```

## Exception Hierarchy

```
GPConfigError (base class)
├── ConfigFolderError
├── ConfigNotFoundError
├── ConfigReadonlyError
├── RegistrationError
└── ConfigValidationError
```

## GPConfigError

Base exception for all gpconfig errors.

```python
class GPConfigError(Exception):
    """Base exception for all gpconfig errors."""
    pass
```

### Usage

Catch all gpconfig-related exceptions:

```python
from gpconfig import GPConfigError, GPConfigManager

try:
    manager = GPConfigManager("myapp")
    config = manager.get_config("database")
except GPConfigError as e:
    print(f"Config error: {e}")
```

## ConfigFolderError

Raised when the config folder cannot be found or is invalid.

```python
class ConfigFolderError(GPConfigError):
    """Raised when the config folder cannot be found or is invalid."""
    pass
```

### Trigger Conditions

- Config folder does not exist
- Config path is not a directory
- Config folder is missing `global_env.yaml`

### Examples

```python
from gpconfig import GPConfigManager, ConfigFolderError
from pathlib import Path

try:
    # Folder doesn't exist
    manager = GPConfigManager("myapp", cfg_folder=Path("/nonexistent"))
except ConfigFolderError as e:
    print(f"Config folder error: {e}")
    # Output: Config folder does not exist: /nonexistent (from explicit parameter)

try:
    # Missing global_env.yaml
    manager = GPConfigManager("myapp", cfg_folder=Path("/tmp"))
except ConfigFolderError as e:
    print(f"Config folder error: {e}")
    # Output: Config folder must contain global_env.yaml: /tmp (from explicit parameter)
```

## ConfigNotFoundError

Raised when a requested config path doesn't exist.

```python
class ConfigNotFoundError(GPConfigError):
    """Raised when a requested config path doesn't exist."""

    def __init__(self, path: str, message: str = ""):
        self.path = path
        super().__init__(message or f"Config not found: {path}")
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | `str` | The config path that was not found |

### Examples

```python
from gpconfig import GPConfigManager, ConfigNotFoundError

manager = GPConfigManager("myapp")

try:
    config = manager.get_config("nonexistent")
except ConfigNotFoundError as e:
    print(f"Config not found: {e.path}")
    print(f"Error message: {e}")

try:
    value = manager.get_config("database.nonexistent_key")
except ConfigNotFoundError as e:
    print(f"Key not found: {e.path}")
```

## ConfigReadonlyError

Raised when trying to save a readonly config.

```python
class ConfigReadonlyError(GPConfigError):
    """Raised when trying to modify or save a readonly config."""

    def __init__(self, config_name: str):
        super().__init__(f"Config '{config_name}' is readonly and cannot be modified")
```

### Examples

```python
from gpconfig import GPConfig, GPConfigManager, ConfigReadonlyError
from typing import ClassVar

class SecureConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "SecureConfig"
    api_key: str

# Get config
manager = GPConfigManager("myapp")
config = manager.get_config("secure", SecureConfig)

# Set as readonly
config.readonly = True

try:
    config.api_key = "new_key"
    config.save()
except ConfigReadonlyError as e:
    print(f"Cannot save readonly config: {e}")
    # Output: Config 'secure' is readonly and cannot be modified
```

### Use Cases

Readonly configs are suitable for:
- Production environment sensitive configs
- System configs that should not be modified
- Preventing accidental overwrites

```python
# Auto-set readonly in production environment
import os

config = manager.get_config("production_db", DatabaseConfig)
if os.environ.get("ENV") == "production":
    config.readonly = True
```

## RegistrationError

Raised when there's an issue with class registration.

```python
class RegistrationError(GPConfigError):
    """Raised when there's an issue with class registration."""
    pass
```

### Trigger Conditions

- Registering duplicate `cfg_class_name`
- Config class not registered but `get_object()` was called
- Config class has no associated `configured_class`

### Examples

```python
from gpconfig import GPConfig, GPConfigManager, RegistrationError
from typing import ClassVar

class MyConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "MyConfig"
    value: str

# First registration - success
GPConfigManager.register_config_class(MyConfig)

# Second registration - failure
try:
    GPConfigManager.register_config_class(MyConfig)
except RegistrationError as e:
    print(f"Registration error: {e}")
    # Output: Config class name 'MyConfig' is already registered
```

## ConfigValidationError

Raised when a config file fails validation.

```python
class ConfigValidationError(GPConfigError):
    """Raised when a config file fails validation."""

    def __init__(self, path: str, original_error: Exception):
        self.path = path
        self.original_error = original_error
        super().__init__(f"Validation failed for '{path}': {original_error}")
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | `str` | The config path that failed validation |
| `original_error` | `Exception` | The original Pydantic validation error |

### Examples

```python
from gpconfig import GPConfig, GPConfigManager, ConfigValidationError
from typing import ClassVar

class ServerConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "ServerConfig"
    host: str      # Required
    port: int      # Must be integer

# Assume server.yaml contains:
# host: localhost
# port: "not_a_number"  # Type error

manager = GPConfigManager("myapp")

try:
    config = manager.get_config("server", ServerConfig)
except ConfigValidationError as e:
    print(f"Config validation failed: {e.path}")
    print(f"Original error: {e.original_error}")
```

## Best Practices

1. **Use specific exception types**: Catch specific exceptions based on the scenario
2. **Provide helpful error messages**: Give user-friendly error messages in exception handlers
3. **Log original errors**: For `ConfigValidationError`, log `original_error` for debugging
4. **Use base class as fallback**: Use `GPConfigError` to catch all unhandled config exceptions
