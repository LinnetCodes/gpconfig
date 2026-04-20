# GPConfig Class

`GPConfig` is the base class for all config classes, built on Pydantic's `BaseSettings`, providing type-safe configuration management.

## Import

```python
from gpconfig import GPConfig
```

## Class Definition

```python
class GPConfig(BaseSettings):
    # Class-level variables
    cfg_class_name: ClassVar[str] = "GPConfig"
    default_cfg_path: ClassVar[Optional[str]] = None

    # Instance fields
    name: str = ""
    cfg_file_path: Path = Path()
    readonly: bool = False
    configured_class_name: Optional[str] = None
```

## Class-Level Variables

### cfg_class_name

An identifier for auto-detecting config classes. Setting this value in YAML files allows automatic association with config classes.

```python
from typing import ClassVar
from gpconfig import GPConfig

class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432
```

Corresponding YAML file:

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
host: localhost
port: 5432
```

### configured_class_name (Instance Field)

The name of the configurable object class associated with this config. This field is stored in YAML files and used by `get_object()` to automatically find the corresponding configurable class.

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
```

```python
from gpconfig import GPConfig, GPConfigManager
from typing import ClassVar

class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432

# Register config class and configurable class
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_configurable_class(Database)

# When loading config, configured_class_name is used to find the corresponding class
manager = GPConfigManager("myapp")
db = manager.get_object("database")  # Automatically uses Database class
```

### default_cfg_path

The default relative path when saving configs.

```python
class CacheConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "CacheConfig"
    default_cfg_path: ClassVar[str] = "cache"  # Save to cache/{name}.yaml
    host: str = "localhost"
```

## Instance Fields

### name

The config name, typically set to the YAML filename (without extension).

```python
config = DatabaseConfig(host="localhost")
config.name = "production"
```

### cfg_file_path

The full path to the config file.

```python
config.cfg_file_path = Path("/etc/myapp/database.yaml")
```

### readonly

Whether this is a readonly config. When set to `True`, calling `save()` will raise an exception.

```python
config = DatabaseConfig(host="localhost", readonly=True)
config.save()  # Raises ConfigReadonlyError
```

## Methods

### save()

Save the current config state back to the YAML file.

```python
def save(self) -> None:
    """Save current config state back to the YAML file.

    Raises:
        ConfigReadonlyError: If readonly is True
    """
```

**Example:**

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigManager

class ServerConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "ServerConfig"
    host: str = "localhost"
    port: int = 8080

# Initialize manager
manager = GPConfigManager("myapp")

# Get config
config = manager.get_config("server", ServerConfig)

# Modify config
config.port = 9000

# Save to file
config.save()
```

**Notes:**

- `save()` excludes `name`, `cfg_file_path`, and `readonly` fields
- `cfg_class_name` is included in the saved YAML
- `configured_class_name` is included if set
- The config must be writable (`readonly=False`)

## Type Validation

GPConfig inherits from Pydantic, supporting full type validation:

```python
from typing import ClassVar, List
from gpconfig import GPConfig

class AppConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "AppConfig"

    # Required field
    app_name: str

    # With default value
    debug: bool = False

    # Various types
    port: int = 8080
    timeout: float = 30.0
    allowed_hosts: List[str] = []

# Validation failure example
from pydantic import ValidationError

try:
    config = AppConfig(app_name="MyApp", port="invalid")
except ValidationError as e:
    print(f"Validation failed: {e}")
```

## Extra Fields Forbidden

By default, GPConfig does not allow undefined fields:

```python
class StrictConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "StrictConfig"
    name: str

# This raises ValidationError
config = StrictConfig(name="test", unknown_field="value")
```

## Complete Example

### Defining and Using Config Classes

```python
from typing import ClassVar
from pathlib import Path
from gpconfig import GPConfig, GPConfigManager

# Define config class
class DatabaseConfig(GPConfig):
    """Database connection configuration"""
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    default_cfg_path: ClassVar[str] = "databases"  # Save to databases/ directory

    host: str
    port: int = 5432
    username: str
    password: str
    database: str
    pool_size: int = 10

# Initialize manager
manager = GPConfigManager("myapp")

# Register config class
GPConfigManager.register_config_class(DatabaseConfig)

# Get config
config = manager.get_config("databases.primary")

print(f"Host: {config.host}")
print(f"Port: {config.port}")
print(f"Database: {config.database}")

# Modify and save
config.pool_size = 20
config.save()

# Use manager to save to new location
new_config = DatabaseConfig(
    host="localhost",
    username="admin",
    password="secret",
    database="test_db"
)
new_config.name = "test"
manager.save(new_config)  # Saves to databases/test.yaml
```

### Readonly Config

```python
# Create readonly config (typically for production sensitive configs)
config = manager.get_config("production_db")
config.readonly = True

# Attempting to save raises an exception
config.port = 5433
config.save()  # ConfigReadonlyError!
```
