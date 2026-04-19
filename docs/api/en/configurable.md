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
class Database(GPConfigable):
    def __init__(self, config: DatabaseConfig) -> None:  # Specific type
        super().__init__(config)
        self.host = config.host  # IDE can autocomplete
```
