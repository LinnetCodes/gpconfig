# gpconfig API Documentation

gpconfig is a general-purpose Python configuration management library built on Pydantic, providing type-safe configuration management.

## Installation

```bash
pip install gpconfig
```

## Core Components

| Component | Description |
|-----------|-------------|
| [`GPConfig`](gpconfig.md) | Base class for all config classes |
| [`GPConfigurable`](configurable.md) | Base class for objects created from configs |
| [`GPConfigManager`](manager.md) | Manages config folder, loading, and object creation |
| [`GPConfigFolder`](manager.md#gpconfigfolder) | Represents a subfolder in the config folder hierarchy |

## Exceptions

| Exception | Description |
|-----------|-------------|
| `GPConfigError` | Base exception for all gpconfig errors |
| `ConfigFolderError` | Config folder not found or invalid |
| `ConfigNotFoundError` | Requested config path does not exist |
| `ConfigReadonlyError` | Attempted to modify readonly config |
| `RegistrationError` | Class registration issues |
| `ConfigValidationError` | Config file validation failed |

See [Exceptions Documentation](exceptions.md) for details.

## Quick Start

### 1. Define Config Classes

```python
from typing import ClassVar
from gpconfig import GPConfig

class DatabaseConfig(GPConfig):
    """Database configuration"""
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432
    username: str
    password: str
    database: str
```

### 2. Create Config Folder

Create a config folder in your project root or user directory, containing `global_env.yaml`:

```
myapp/
├── global_env.yaml    # Required: global environment config
├── database.yaml      # Your config files
└── llm/               # Nested configs
    ├── openai.yaml
    └── anthropic.yaml
```

**global_env.yaml example:**

```yaml
version: "1.0.0"
debug: true
log_level: INFO
```

**database.yaml example:**

```yaml
cfg_class_name: "DatabaseConfig"
host: localhost
port: 5432
username: admin
password: secret
database: myapp
```

### 3. Initialize Config Manager

```python
from pathlib import Path
from gpconfig import GPConfigManager

# Option 1: Specify config folder path
manager = GPConfigManager("myapp", cfg_folder=Path("/path/to/configs"))

# Option 2: Use environment variable MYAPP_CFG_PATH
manager = GPConfigManager("myapp")

# Option 3: Use myapp folder in user directory (~/.myapp/)
manager = GPConfigManager("myapp")
```

### 4. Read Configs

```python
# Read values from global_env
debug = manager.get_config("global_env.debug")
version = manager.get_config("global_env.version")

# Load config file (auto-detect by cfg_class_name)
db_config = manager.get_config("database")

# Load with specific config class
db_config = manager.get_config("database", DatabaseConfig)

# Load nested config
llm_config = manager.get_config("llm.openai")

# Read specific field
host = manager.get_config("database.host")
```

### 5. Define Configurable Objects

```python
from gpconfig import GPConfigurable

class Database(GPConfigurable):
    """Database connection object"""

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        self.database = config.database

    @property
    def connection_string(self) -> str:
        return (
            f"postgresql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )
```

### 6. Register and Create Objects

```python
# Register config class
GPConfigManager.register_config_class(DatabaseConfig)

# Register configurable class (just pass the class itself)
GPConfigManager.register_configurable_class(Database)

# Create object instance from config
db = manager.get_object("database")
print(db.connection_string)
# Output: postgresql://admin:secret@localhost:5432/myapp
```

**Note:** Your config file needs a `configured_class_name` field:

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
username: admin
password: secret
database: myapp
```

### 7. Save Configs

```python
# Get config and modify
db_config = manager.get_config("database", DatabaseConfig)
db_config.port = 5433

# Save back to file
db_config.save()

# Or use manager to save to new location
manager.save(db_config, "backups/database_backup")
```

## Config Folder Search Rules

GPConfigManager searches for config folder in this order:

1. **Explicit parameter** - `cfg_folder` parameter in constructor
2. **Environment variable** - `{PROJECT_NAME}_CFG_PATH` (uppercase)
3. **User directory** - `~/{project_name}/`

A valid config folder must contain `global_env.yaml` file.

## Type Safety

gpconfig is built on Pydantic, providing full type validation:

```python
class ServerConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "ServerConfig"
    host: str                    # Required field
    port: int = 8080             # With default value
    debug: bool = False          # Boolean type
    timeout: float = 30.0        # Float type

# Type mismatch throws ConfigValidationError
config = ServerConfig(host="localhost", port="invalid")  # Error!
```

## Complete Example

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigurable, GPConfigManager

# 1. Define config class
class CacheConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "CacheConfig"
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""

# 2. Define configurable object
class Cache(GPConfigurable):
    def __init__(self, config: CacheConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port
        self.db = config.db
        self.password = config.password

    def connect(self):
        print(f"Connecting to Redis at {self.host}:{self.port}")

# 3. Initialize manager
manager = GPConfigManager("myapp")

# 4. Register classes (separately register config class and configurable class)
GPConfigManager.register_config_class(CacheConfig)
GPConfigManager.register_configurable_class(Cache)

# 5. Use config
cache = manager.get_object("cache")
cache.connect()
```

**cache.yaml config file:**

```yaml
cfg_class_name: "CacheConfig"
configured_class_name: "Cache"
host: localhost
port: 6379
db: 0
password: ""
```
