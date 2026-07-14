# Exceptions

gpconfig defines a set of custom exception classes for handling various error scenarios during configuration management.

## Import

```python
from gpconfig import (
    GPConfigError,
    ConfigFolderError,
    ConfigNotFoundError,
    IllegalPathError,
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
├── IllegalPathError
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

## IllegalPathError

Raised when a config path is malformed or escapes the `cfg_folder` (defence-in-depth containment).

```python
class IllegalPathError(GPConfigError):
    """Raised when a config path is malformed or escapes the cfg_folder."""

    def __init__(self, path: str, message: str = ""):
        self.path = path
        super().__init__(message or f"Illegal config path: {path}")
```

### Trigger Conditions

A path is considered malformed and raises `IllegalPathError` when it is:

- **Empty** — e.g. `""` (was previously a tolerated way to refer to the root folder).
- **Dots-only** — e.g. `"."`, `".."`.
- **Contains consecutive dots** — e.g. `"a..b"`.
- **Has a leading or trailing dot** — e.g. `".x"`, `"x."` (a trailing dot previously returned the entire `global_env` dict by accident).
- **Contains a literal `/` or `\` in cfg_path style** — cfg_path uses dot-notation; a raw separator signals a malformed path.

Additionally, even a syntactically valid path raises `IllegalPathError` if it **resolves outside the `cfg_folder`**. This containment check is a defence-in-depth guarantee that no path can escape the managed folder.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | `str` | The offending path string that was rejected |

### Raised By

`IllegalPathError` is raised by `GPConfigManager.get_config()`, `get_object()`, `list_configs()`, and `save()` whenever they encounter a malformed or escaping path.

### Examples

```python
from gpconfig import GPConfigManager, IllegalPathError

manager = GPConfigManager("myapp")

# Malformed paths
for bad in ["", ".", "a..b", ".hidden", "global_env.", "a/b"]:
    try:
        manager.get_config(bad)
    except IllegalPathError as e:
        print(f"Rejected {bad!r}: {e.path} -> {e}")

# save() rejects path containing '.' (cfg_path style, '.yaml' suffix, '..' traversal)
try:
    manager.save(config, "backups/database.yaml")  # contains '.' (.yaml suffix)
except IllegalPathError as e:
    print(f"Save rejected: {e}")
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

- Registering a **different** class under an already-registered `cfg_class_name` (re-registering the same class is idempotent and succeeds silently)
- Config class not registered but `get_object()` was called
- Config class has no associated `configured_class`

### Examples

```python
from gpconfig import GPConfig, GPConfigManager, RegistrationError
from typing import ClassVar

class MyConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "MyConfig"
    value: str

class ConflictConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "MyConfig"  # same cfg_class_name, different class
    other: str

# First registration - success
GPConfigManager.register_config_class(MyConfig)

# Second registration with a DIFFERENT class under the same name - failure
try:
    GPConfigManager.register_config_class(ConflictConfig)
except RegistrationError as e:
    print(f"Registration error: {e}")
    # Output: Config class name 'MyConfig' is already registered with a different class
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

### Trigger Conditions

`ConfigValidationError` is raised by `GPConfigManager.get_config()` (and the YAML loading path it uses) whenever a config file cannot be turned into a valid config object:

- **YAML syntax/parse error** — malformed YAML (bad indentation, unclosed quotes/brackets, tabs). The original error is a `yaml.YAMLError`, whose message carries the file path, line, and column (e.g. `in ".../server.yaml", line 3, column 5`).
- **Non-dict top level** — the YAML parses but its root is a list or scalar instead of a mapping. The message embeds the on-disk file path.
- **Pydantic validation failure** — the YAML parses to a dict but a field fails schema validation (wrong type, missing required field, or an extra key under `extra="forbid"`). The original error is a Pydantic `ValidationError`, whose message names the offending field.

In all cases the exception message carries the **dotted config path** (on `.path`), the **on-disk file path**, and the underlying error's detail (field name and/or line number) so you can locate the problem precisely.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | `str` | The dotted config path that failed validation |
| `original_error` | `Exception` | The underlying error: a Pydantic `ValidationError`, a `yaml.YAMLError`, or a `TypeError` (non-dict top level) |

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
    # e.path is the dotted config path, e.g. "server".
    # str(e) also embeds the on-disk file path and the offending field name.
    print(f"Original error: {e.original_error}")
```

## Best Practices

1. **Use specific exception types**: Catch specific exceptions based on the scenario
2. **Provide helpful error messages**: Give user-friendly error messages in exception handlers
3. **Log original errors**: For `ConfigValidationError`, log `original_error` for debugging
4. **Use base class as fallback**: Use `GPConfigError` to catch all unhandled config exceptions
