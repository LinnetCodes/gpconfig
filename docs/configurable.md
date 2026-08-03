# GPConfigurable Class

`GPConfigurable` is the base class for all configurable objects. By inheriting from this class, you can create objects that are instantiated from `GPConfig` configurations.

## Import

```python
from gpconfig import GPConfigurable
```

## Class Definition

```python
class GPConfigurable:
    def __init__(self, config: "GPConfig") -> None:
        """Initialize the configurable object from its config."""
        self._config = config

    @property
    def config(self) -> "GPConfig":
        """Access the configuration object."""
        return self._config
```

## Usage Pattern

### Basic Usage

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigurable, GPConfigManager

# 1. Define config class
class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432
    username: str
    password: str
    database: str

# 2. Define configurable object class
class Database(GPConfigurable):
    """Database connection object"""

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        self.database = config.database
        self._connection = None

    def connect(self):
        """Establish database connection"""
        print(f"Connecting to {self.host}:{self.port}/{self.database}")
        # Actual connection logic...

    def close(self):
        """Close connection"""
        if self._connection:
            self._connection.close()
```

### Register and Create Objects

```python
# 3. Initialize manager
manager = GPConfigManager("myapp")

# 4. Register config class and configurable class (separately)
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_configurable_class(Database)

# 5. Create object instance from config
db = manager.get_object("database")

# Use the object
db.connect()
```

**Config file (database.yaml):**

```yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
username: admin
password: secret
database: myapp
```

## config Property

Access the original config object through the `config` property:

```python
class Cache(GPConfigurable):
    def __init__(self, config: "CacheConfig") -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port

    def reconnect(self):
        # Access config through config property
        print(f"Reconnecting to {self.config.host}:{self.config.port}")

cache = manager.get_object("cache")
print(cache.config.ttl)  # Access field from config
```

## Context-Aware Construction

### When to Override `from_config()`

Most subclasses do **not** need to override anything. The default
`GPConfigurable.from_config(config, *, context)` simply calls `cls(config)`, so a
standard single-argument subclass keeps working unchanged:

```python
class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)   # nothing else required
```

Override `from_config()` **only when** the object must reference other configs in
the same config tree at construction time. The `context` argument is the only way
for the object to reach the manager that built it — `GPConfig` carries no manager
field by design.

### The Construction Hook and Context

```python
from gpconfig import GPConfigurable, GPConfigurableContext


class Worker(GPConfigurable):
    @classmethod
    def from_config(
        cls,
        config: WorkerConfig,
        *,
        context: GPConfigurableContext,
    ) -> "Worker":
        # context.manager: the GPConfigManager that received this get_object() call.
        # context.path:    canonical dotted path of this object's YAML file,
        #                  with the .yaml suffix and any project-name prefix stripped
        #                  (e.g. "services.api" and "myapp.services.api" both give
        #                  context.path == "services.api").
        return cls(config)
```

`GPConfigurableContext` is a frozen, slotted value object with exactly two fields:

| Field     | Meaning                                                                                  |
|-----------|------------------------------------------------------------------------------------------|
| `manager` | The `GPConfigManager` that received this `get_object()` request.                         |
| `path`    | Canonical dotted path of the source YAML file (no `.yaml`, no project-name prefix).      |

### Example: Referencing Another Config

A `Worker` that needs the database config. It reads it through
`context.manager.get_config(...)`, which returns the config **data** without
constructing a `Database` object:

```python
from typing import ClassVar

from gpconfig import GPConfig, GPConfigurable, GPConfigManager
from gpconfig.configurable import GPConfigurableContext


class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432


class WorkerConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "WorkerConfig"
    worker_name: str
    concurrency: int = 4


class Worker(GPConfigurable):
    def __init__(self, config: WorkerConfig) -> None:
        super().__init__(config)
        self.worker_name = config.worker_name
        self.concurrency = config.concurrency
        self.database = None

    @classmethod
    def from_config(
        cls,
        config: WorkerConfig,
        *,
        context: GPConfigurableContext,
    ) -> "Worker":
        db_config = context.manager.get_config("database", DatabaseConfig)
        obj = cls(config)
        obj.database = db_config
        return obj
```

**YAML files:**

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
host: db.internal
port: 5432
```

```yaml
# worker.yaml
cfg_class_name: "WorkerConfig"
configured_class_name: "Worker"
worker_name: ingest
concurrency: 8
```

```python
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_config_class(WorkerConfig)
GPConfigManager.register_configurable_class(Worker)

manager = GPConfigManager("myapp")
worker = manager.get_object("worker")
print(worker.worker_name)        # ingest
print(worker.database.host)     # db.internal
```

### Choosing Between `get_config` and `get_object` Inside a Hook

The two manager calls a hook can make behave very differently:

| Call                                     | Calls `from_config`? | Recurses? | Cached?                  |
|------------------------------------------|:--------------------:|:---------:|--------------------------|
| `context.manager.get_config(path, Cfg)`  | No                   | No        | Yes — config data, per file |
| `context.manager.get_object(path)`       | Yes                  | Yes       | No — a new object each call |

Use `get_config` to read another config's **data**. Use `get_object` only when you
need another fully-constructed **object** (and accept that it recurses through
*its* `from_config`).

### Important Constraints

- The hook **must** return an instance of the registered configurable class (a
  subclass instance is also allowed). Any other return value raises
  `ConfigurableConstructionError`.
- Exceptions raised by the hook — including `TypeError` from an incompatible
  signature — propagate unchanged. The manager never retries the legacy
  `cls(config)` constructor after a hook fails.
- `get_object()` does **not** cache objects; every call returns a fresh instance.
  `get_config()` **does** cache config data per file.
- **Cycle detection is the caller's responsibility.** The manager performs no
  cycle detection or depth limiting. If `get_object("a")`'s hook calls
  `get_object("b")` whose hook calls back `get_object("a")`, it recurses without
  bound and overflows the stack.

> The default `from_config()` preserves the standard-subclass contract, so most
> users never need to override it.

## Complete Example

### Multiple Configurable Objects

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigurable, GPConfigManager

# Config class
class LLMConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "LLMConfig"
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096

# Configurable object
class LLMProvider(GPConfigurable):
    """LLM Provider"""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self.api_key = config.api_key
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    def generate(self, prompt: str) -> str:
        """Generate text"""
        print(f"Using model: {self.model}")
        print(f"Temperature: {self.temperature}")
        # Actual LLM API call...
        return f"Response to: {prompt}"

# Initialize
manager = GPConfigManager("myapp")

# Register config class and configurable class separately
GPConfigManager.register_config_class(LLMConfig)
GPConfigManager.register_configurable_class(LLMProvider)

# Create different objects using different configs
openai = manager.get_object("llm.openai")
anthropic = manager.get_object("llm.anthropic")

print(openai.model)      # gpt-4
print(anthropic.model)   # claude-3-opus
```

**YAML config files:**

```yaml
# llm/openai.yaml
cfg_class_name: "LLMConfig"
configured_class_name: "LLMProvider"
api_key: sk-xxx
model: gpt-4
temperature: 0.7
max_tokens: 4096
```

```yaml
# llm/anthropic.yaml
cfg_class_name: "LLMConfig"
configured_class_name: "LLMProvider"
api_key: sk-yyy
model: claude-3-opus
temperature: 0.8
max_tokens: 8192
```

### Accessing Config Metadata

```python
class Service(GPConfigurable):
    def __init__(self, config: "ServiceConfig") -> None:
        super().__init__(config)
        self.name = config.name  # Config name
        self.url = config.url

    def info(self):
        return {
            "name": self.name,
            "config_file": str(self.config.cfg_file_path),
            "url": self.url
        }

service = manager.get_object("api_service")
print(service.info())
# {'name': 'api_service', 'config_file': '/path/to/api_service.yaml', 'url': '...'}
```

## Notes

### Each Call Creates New Instance

`get_object()` creates a new object instance on each call:

```python
db1 = manager.get_object("database")
db2 = manager.get_object("database")

print(db1 is db2)  # False - different instances
```

### Must Call super().__init__()

Subclasses must call the parent class's `__init__` method:

```python
class MyConfigurable(GPConfigurable):
    def __init__(self, config: MyConfig) -> None:
        super().__init__(config)  # Must call
        # Initialization logic...
```

### Type Hints

It's recommended to add type hints for the config parameter for better IDE support:

```python
class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:  # Specific type
        super().__init__(config)
        self.host = config.host  # IDE can autocomplete
```
