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

### Trigger Conditions

- Config file doesn't exist
- Config key path doesn't exist
- Folder doesn't exist

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

### Trigger Conditions

- Calling `save()` on a config with `readonly=True`

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

```python
# Calling get_object() but not registered
try:
    obj = manager.get_object("some_config")
except RegistrationError as e:
    print(f"Error: {e}")
    # Output: Config at path 'some_config' was loaded as dict (no registered config class)
```

```python
# Config class has no configured_class_name
GPConfigManager.register_config_class(MyConfig)  # Only register config class
# But config file is missing configured_class_name field

try:
    obj = manager.get_object("my_config")
except RegistrationError as e:
    print(f"Error: {e}")
    # Output: No configured_class_name found in config at path 'my_config'
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

### Trigger Conditions

- Config file content doesn't match config class types
- Missing required fields
- Field type conversion failed

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

```python
# Missing required field
# Assume server.yaml contains:
# port: 8080
# Missing host field

try:
    config = manager.get_config("server", ServerConfig)
except ConfigValidationError as e:
    print(f"Missing required field: {e}")
```

## Complete Exception Handling Example

```python
from gpconfig import (
    GPConfig,
    GPConfigurable,
    GPConfigManager,
    GPConfigError,
    ConfigFolderError,
    ConfigNotFoundError,
    ConfigReadonlyError,
    RegistrationError,
    ConfigValidationError,
)
from typing import ClassVar

class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432

class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port

def get_database():
    """Get database connection with complete error handling"""
    try:
        manager = GPConfigManager("myapp")
        # Register config class and configurable class separately
        GPConfigManager.register_config_class(DatabaseConfig)
        GPConfigManager.register_configurable_class(Database)
        return manager.get_object("database")

    except ConfigFolderError as e:
        print(f"Config folder issue: {e}")
        print("Please ensure config folder exists and contains global_env.yaml")
        return None

    except ConfigNotFoundError as e:
        print(f"Config not found: {e.path}")
        print("Please check if config file exists")
        return None

    except ConfigValidationError as e:
        print(f"Config validation failed: {e.path}")
        print(f"Details: {e.original_error}")
        return None

    except RegistrationError as e:
        print(f"Registration error: {e}")
        print("Please ensure config class and configurable class are properly registered")
        return None

    except ConfigReadonlyError as e:
        print(f"Readonly config: {e}")
        return None

    except GPConfigError as e:
        # Catch all other gpconfig exceptions
        print(f"Config error: {e}")
        return None

# Usage
db = get_database()
if db:
    print(f"Connected to {db.host}:{db.port}")
```

**Config file example (database.yaml):**

```yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
```

## Best Practices

1. **Use specific exception types**: Catch specific exceptions based on the scenario
2. **Provide helpful error messages**: Give user-friendly error messages in exception handlers
3. **Log original errors**: For `ConfigValidationError`, log `original_error` for debugging
4. **Use base class as fallback**: Use `GPConfigError` to catch all unhandled config exceptions
