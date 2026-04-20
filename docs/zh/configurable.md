# GPConfigurable 类

`GPConfigurable` 是所有可配置对象的基类。通过继承此类，可以创建从 `GPConfig` 配置实例化的对象。

## 导入

```python
from gpconfig import GPConfigurable
```

## 类定义

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

## 使用模式

### 基本用法

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigurable, GPConfigManager

# 1. 定义配置类
class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432
    username: str
    password: str
    database: str

# 2. 定义可配置对象类
class Database(GPConfigurable):
    """数据库连接对象"""

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        self.database = config.database
        self._connection = None

    def connect(self):
        """建立数据库连接"""
        print(f"Connecting to {self.host}:{self.port}/{self.database}")
        # 实际连接逻辑...

    def close(self):
        """关闭连接"""
        if self._connection:
            self._connection.close()
```

### 注册并创建对象

```python
# 3. 初始化管理器
manager = GPConfigManager("myapp")

# 4. 注册配置类和可配置类（分别注册）
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_configurable_class(Database)

# 5. 从配置创建对象实例
db = manager.get_object("database")

# 使用对象
db.connect()
```

**配置文件 (database.yaml)：**

```yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
username: admin
password: secret
database: myapp
```

## config 属性

通过 `config` 属性可以访问原始配置对象：

```python
class Cache(GPConfigurable):
    def __init__(self, config: "CacheConfig") -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port

    def reconnect(self):
        # 通过 config 属性访问配置
        print(f"Reconnecting to {self.config.host}:{self.config.port}")

cache = manager.get_object("cache")
print(cache.config.ttl)  # 访问配置中的字段
```

## 完整示例

### 多个可配置对象

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigurable, GPConfigManager

# 配置类
class LLMConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "LLMConfig"
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096

# 可配置对象
class LLMProvider(GPConfigurable):
    """LLM 提供者"""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self.api_key = config.api_key
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    def generate(self, prompt: str) -> str:
        """生成文本"""
        print(f"Using model: {self.model}")
        print(f"Temperature: {self.temperature}")
        # 实际调用 LLM API...
        return f"Response to: {prompt}"

# 初始化
manager = GPConfigManager("myapp")

# 分别注册配置类和可配置类
GPConfigManager.register_config_class(LLMConfig)
GPConfigManager.register_configurable_class(LLMProvider)

# 使用不同的配置创建不同的对象
openai = manager.get_object("llm.openai")
anthropic = manager.get_object("llm.anthropic")

print(openai.model)      # gpt-4
print(anthropic.model)   # claude-3-opus
```

**YAML 配置文件：**

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

### 访问配置元数据

```python
class Service(GPConfigurable):
    def __init__(self, config: "ServiceConfig") -> None:
        super().__init__(config)
        self.name = config.name  # 配置名称
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

## 注意事项

### 每次调用创建新实例

`get_object()` 每次调用都会创建新的对象实例：

```python
db1 = manager.get_object("database")
db2 = manager.get_object("database")

print(db1 is db2)  # False - 不同的实例
```

### 必须调用 super().__init__()

子类必须调用父类的 `__init__` 方法：

```python
class MyConfigurable(GPConfigurable):
    def __init__(self, config: MyConfig) -> None:
        super().__init__(config)  # 必须调用
        # 初始化逻辑...
```

### 类型提示

建议为 config 参数添加类型提示以获得更好的 IDE 支持：

```python
class Database(GPConfigable):
    def __init__(self, config: DatabaseConfig) -> None:  # 具体类型
        super().__init__(config)
        self.host = config.host  # IDE 可以自动补全
```
