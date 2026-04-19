# GPConfigManager Class

`GPConfigManager` is the core class for configuration management, responsible for config folder parsing, config loading, class registration, and object creation.

## Import

```python
from gpconfig import GPConfigManager
```

## Class Definition

```python
class GPConfigManager:
    # Class-level registries
    _config_classes: dict[str, Type[Any]] = {}
    _configurable_classes: dict[str, Type[Any]] = {}

    def __init__(self, project_name: str, cfg_folder: Optional[Path | str] = None):
        """Initialize the configuration manager"""
```

## Initialization

### Constructor Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_name` | `str` | Project name, used for environment variables and directory naming |
| `cfg_folder` | `Path \| str \| None` | Optional config folder path |

### Config Folder Search Rules

The config folder is searched in this order:

1. **Explicit parameter** - `cfg_folder` parameter
2. **Environment variable** - `{PROJECT_NAME}_CFG_PATH` (uppercase)
3. **User directory** - `~/{project_name}/`

### Examples

```python
from pathlib import Path
from gpconfig import GPConfigManager

# Option 1: Explicitly specify path
manager = GPConfigManager("myapp", cfg_folder=Path("/etc/myapp"))

# Option 2: Use environment variable MYAPP_CFG_PATH
# export MYAPP_CFG_PATH=/path/to/configs
manager = GPConfigManager("myapp")

# Option 3: Use user directory
# Config folder: ~/myapp/
manager = GPConfigManager("myapp")
```

### Config Folder Requirements

A valid config folder must:
- Exist and be a directory
- Contain a `global_env.yaml` file

```
myapp/
├── global_env.yaml    # Required
├── database.yaml
└── llm/
    └── openai.yaml
```

## Properties

### project_name

Get the project name.

```python
manager = GPConfigManager("myapp")
print(manager.project_name)  # "myapp"
```

### cfg_folder

Get the full path to the config folder.

```python
print(manager.cfg_folder)  # Path("/path/to/configs")
```

### global_env

Get the global environment config dictionary.

```python
# global_env.yaml content:
# version: "1.0.0"
# debug: true

print(manager.global_env["version"])  # "1.0.0"
print(manager.global_env["debug"])    # True
```

## Class Methods

### register_config_class()

Register a config class (without configurable object mapping).

```python
@classmethod
def register_config_class(cls, config_cls: Type[Any]) -> None:
    """Register a config class by its cfg_class_name."""
```

**Example:**

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigManager

class AppConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "AppConfig"
    debug: bool = False

# Register config class
GPConfigManager.register_config_class(AppConfig)

# Now can auto-detect and load
manager = GPConfigManager("myapp")
config = manager.get_config("app")  # Automatically uses AppConfig class
```

### register_configurable_class()

Register a configurable object class. Just pass the configurable class itself, the system will look it up by class name.

```python
@classmethod
def register_configurable_class(
    cls,
    configurable_cls: Type[Any]
) -> None:
    """Register a configurable class by its class name."""
```

**Example:**

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigurable, GPConfigManager

class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432

class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port

# Register config class
GPConfigManager.register_config_class(DatabaseConfig)

# Register configurable class (just pass the class itself)
GPConfigManager.register_configurable_class(Database)
```

**YAML config file:**

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
```

When calling `get_object("database")`, the system will:
1. Load config, read `cfg_class_name` and `configured_class_name`
2. Look up the corresponding class in `_configurable_classes` by `configured_class_name`
3. Create an object instance using the found class

### make_new_project_config_folder()

Create a new project configuration folder.

```python
@classmethod
def make_new_project_config_folder(
    cls,
    project_name: str,
    cfgs: List["GPConfig"],
    global_env: Optional[dict] = None,
    cfg_folder_path: Optional[str | Path] = None,
) -> Path:
    """Create a new project configuration folder with initial configs."""
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_name` | `str` | Project name |
| `cfgs` | `List[GPConfig]` | List of GPConfig instances, each must have `name` |
| `global_env` | `dict \| None` | Content for global_env.yaml |
| `cfg_folder_path` | `str \| Path \| None` | Optional config folder path |

**Returns:** Created config folder path

**Example:**

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigManager

class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str = "localhost"
    port: int = 5432

class CacheConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "CacheConfig"
    default_cfg_path: ClassVar[str] = "cache"
    host: str = "localhost"
    port: int = 6379

# Create config instances
db_config = DatabaseConfig()
db_config.name = "database"

cache_config = CacheConfig()
cache_config.name = "redis"

# Create project config folder
folder = GPConfigManager.make_new_project_config_folder(
    project_name="myapp",
    cfgs=[db_config, cache_config],
    global_env={"version": "1.0.0", "debug": True}
)

# Result:
# ~/myapp/
# ├── global_env.yaml
# ├── database.yaml
# └── cache/
#     └── redis.yaml
```

**Path Resolution Rules:**

1. Explicit parameter `cfg_folder_path`
2. Environment variable `{PROJECT_NAME}_CFG_PATH`
3. User home directory `~/{project_name}/`

**Exceptions:**

| Exception | Trigger Condition |
|-----------|-------------------|
| `ConfigFolderError` | Config folder already exists |
| `ValueError` | Config's `name` is empty |
| `ConfigReadonlyError` | Config has `readonly=True` |

## Instance Methods

### get_config()

Get a config object or config value.

```python
def get_config(
    self,
    path: str,
    config_cls: Optional[Type[T]] = None
) -> Union[T, Any]:
    """Get a config object or a specific config value."""
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Config path, supports dot notation |
| `config_cls` | `Type[T] \| None` | Optional config class |

**Returns:**
- If `config_cls` is specified or auto-detected, returns a config object instance
- If path points to a specific key, returns that key's value
- Otherwise returns the raw dictionary

**Examples:**

```python
# Read values from global_env
debug = manager.get_config("global_env.debug")
version = manager.get_config("global_env.version")

# Read entire config file (auto-detect class)
config = manager.get_config("database")

# Read config file (specify class)
config = manager.get_config("database", DatabaseConfig)

# Read nested config
config = manager.get_config("llm.openai", LLMConfig)

# Read specific value from config
host = manager.get_config("database.host")
model = manager.get_config("llm.anthropic.model")
```

### get_object()

Get a configurable object instance from a config path. The system reads the class name from the config instance's `configured_class_name` field and looks it up in the registry.

```python
def get_object(self, path: str) -> Any:
    """Get a configurable object instance from a config path."""
```

**Example:**

```python
# Register config class and configurable class
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_configurable_class(Database)

# Create object - config file needs configured_class_name: "Database"
db = manager.get_object("database")
print(db.host)  # Value from config

# Nested config
llm = manager.get_object("llm.openai")
```

**Config file example:**

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"  # Must set this to use get_object()
host: localhost
port: 5432
```

**Note:**
- Each call creates a new instance
- Config file must contain `configured_class_name` field
- The class corresponding to `configured_class_name` must be registered via `register_configurable_class()`

### list_configs()

List all config objects in a folder.

```python
def list_configs(self, path: str = "") -> list[str]:
    """List all config objects in a folder."""
```

**Examples:**

```python
# List root directory
items = manager.list_configs()
# ['database', 'llm', 'cache']

# List subdirectory
llm_items = manager.list_configs("llm")
# ['openai', 'anthropic']

# Use dot notation
llm_items = manager.list_configs("services.llm")
# ['openai', 'anthropic']
```

### save()

Save a config to a file.

```python
def save(self, config: "GPConfig", path: Optional[str] = None) -> None:
    """Save a GPConfig instance to a config file."""
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `GPConfig` | Config instance to save |
| `path` | `str \| None` | Optional relative path |

**Examples:**

```python
# Get and modify config
config = manager.get_config("database", DatabaseConfig)
config.port = 5433

# Save (using original path)
manager.save(config)

# Save to new path
manager.save(config, "backups/database_backup")

# Save new config
new_config = DatabaseConfig(
    host="localhost",
    username="admin",
    password="secret",
    database="test"
)
new_config.name = "test"
manager.save(new_config)  # Save to default_cfg_path/test.yaml
```

## Complete Example

### Basic Workflow

```python
from typing import ClassVar
from pathlib import Path
from gpconfig import GPConfig, GPConfigurable, GPConfigManager

# 1. Define config classes
class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432
    username: str
    password: str
    database: str

class LLMConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "LLMConfig"
    api_key: str
    model: str
    temperature: float = 0.7

# 2. Define configurable objects
class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        self.database = config.database

class LLMProvider(GPConfigurable):
    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self.api_key = config.api_key
        self.model = config.model
        self.temperature = config.temperature

# 3. Initialize manager
manager = GPConfigManager("myapp")

# 4. Register classes (separately register config class and configurable class)
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_configurable_class(Database)
GPConfigManager.register_config_class(LLMConfig)
GPConfigManager.register_configurable_class(LLMProvider)

# 5. Read configs
debug = manager.get_config("global_env.debug")
print(f"Debug mode: {debug}")

db_config = manager.get_config("database")
print(f"Database host: {db_config.host}")

# 6. Create objects (config file needs configured_class_name)
db = manager.get_object("database")
llm = manager.get_object("llm.openai")

# 7. List configs
for item in manager.list_configs():
    print(f"Found: {item}")

# 8. Save config
db_config.port = 5433
db_config.save()
```

### YAML Config File Examples

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

```yaml
# llm/openai.yaml
cfg_class_name: "LLMConfig"
configured_class_name: "LLMProvider"
api_key: sk-xxx
model: gpt-4
temperature: 0.7
```

### Environment Variable Configuration

```python
import os

# Set environment variable
os.environ["MYAPP_CFG_PATH"] = "/etc/myapp/configs"

# Manager automatically uses the environment variable
manager = GPConfigManager("myapp")
print(manager.cfg_folder)  # /etc/myapp/configs
```

### Creating New Configs

```python
# Create new config
new_db_config = DatabaseConfig(
    host="localhost",
    username="admin",
    password="secret",
    database="test_db",
    port=5433
)
new_db_config.name = "test_database"

# Save to file
manager.save(new_db_config)

# Now can load it
loaded = manager.get_config("test_database")
```

## GPConfigFolder

Represents a subfolder in the config folder hierarchy. Provides convenient access to configs within a specific folder.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Relative path from cfg_folder using dot notation (e.g., "llm.providers") |

### Methods

#### `__init__(manager, relative_path)`

Initialize GPConfigFolder.

| Parameter | Type | Description |
|-----------|------|-------------|
| `manager` | `GPConfigManager` | The GPConfigManager instance |
| `relative_path` | `str` | Relative path from cfg_folder using dot notation |

#### `get_config(path, config_cls=None)`

Get a config object or value from this folder.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Config path relative to this folder |
| `config_cls` | `Type[T]` | Optional GPConfig subclass to use for loading |

**Returns:** `GPConfig` instance, `GPConfigFolder`, or config value.

#### `get_object(path)`

Get a configurable object instance from this folder.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Config path relative to this folder |

**Returns:** A new instance of the configured GPConfigurable subclass.

#### `list_configs()`

List all config objects in this folder.

**Returns:** `List[str]` - List of object names (config names and subfolder names).
