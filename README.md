# gpconfig

[简体中文](README.zh-CN.md) | English

General Purpose Configuration management library for Python projects.

A type-safe, YAML-based configuration management library built on Pydantic.

## Features

- **Type-safe configuration** - Built on Pydantic with full type validation
- **YAML-based** - Human-readable configuration files
- **Nested configs** - Organize configs in directories (e.g., `llm/openai.yaml`)
- **Auto-detection** - Automatically detect config classes from YAML files
- **Configurable objects** - Create object instances directly from configs
- **Environment variable support** - Configure paths via environment variables
- **Readonly configs** - Protect sensitive configurations

## Installation

```bash
pip install gpconfig
```

## Quick Start

### 1. Define Config Classes

```python
from typing import ClassVar
from gpconfig import GPConfig

class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432
    username: str
    password: str
    database: str
```

### 2. Create Config Folder

```
myapp/
├── global_env.yaml    # Required: global environment config
├── database.yaml      # Your config files
└── llm/               # Nested configs
    ├── openai.yaml
    └── anthropic.yaml
```

**global_env.yaml:**
```yaml
version: "1.0.0"
debug: true
log_level: INFO
```

**database.yaml:**
```yaml
cfg_class_name: "DatabaseConfig"
host: localhost
port: 5432
username: admin
password: secret
database: myapp
```

### 3. Initialize Manager and Load Configs

```python
from gpconfig import GPConfigManager

# Config folder search order:
# 1. Explicit cfg_folder parameter
# 2. Environment variable: {PROJECT_NAME}_CFG_PATH
# 3. User directory: ~/.{project_name}/
manager = GPConfigManager("myapp", cfg_folder="/path/to/myapp")

# Read global_env values
debug = manager.get_config("global_env.debug")

# Load config (auto-detect class by cfg_class_name)
db_config = manager.get_config("database")

# Load nested config
llm_config = manager.get_config("llm.openai")

# Read specific field
host = manager.get_config("database.host")
```

### 4. Create Configurable Objects

```python
from gpconfig import GPConfigurable

class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        self.database = config.database

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

# Register classes
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_configurable_class(Database)

# Create object instance
db = manager.get_object("database")
print(db.connection_string)
```

**Note:** Add `configured_class_name` to your YAML for `get_object()`:

```yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
```

### 5. Save Configs

```python
# Modify and save
db_config.port = 5433
db_config.save()

# Save to new location
manager.save(db_config, "backups/database_backup")
```

## Core Components

| Component | Description |
|-----------|-------------|
| `GPConfig` | Base class for all config classes |
| `GPConfigurable` | Base class for objects created from configs |
| `GPConfigManager` | Manages config folder, loading, and object creation |

## Exceptions

| Exception | Description |
|-----------|-------------|
| `GPConfigError` | Base exception for all gpconfig errors |
| `ConfigFolderError` | Config folder not found or invalid |
| `ConfigNotFoundError` | Requested config path does not exist |
| `ConfigReadonlyError` | Attempted to modify readonly config |
| `RegistrationError` | Class registration issues |
| `ConfigValidationError` | Config file validation failed |

## API Reference

See the [API documentation](docs/index.md) for detailed usage.

## License

MIT
