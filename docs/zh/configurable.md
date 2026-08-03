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

## 上下文感知构造

### 何时重写 `from_config()`

大多数子类**不需要**重写任何东西。默认的
`GPConfigurable.from_config(config, *, context)` 只是调用 `cls(config)`，所以标准的
单参数子类无需任何改动即可继续工作：

```python
class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)   # 无需其它代码
```

**仅当**对象在构造时需要引用同一配置树中的其它配置时，才需要重写 `from_config()`。
`context` 参数是对象访问构造它的 manager 的唯一途径——按设计 `GPConfig` 不携带 manager 字段。

### 构造钩子与上下文

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
        # context.manager：接收本次 get_object() 调用的 GPConfigManager。
        # context.path：   本对象 YAML 文件的规范点路径，
        #                  去掉了 .yaml 后缀和可选的项目名前缀
        #                  （例如 "services.api" 和 "myapp.services.api"
        #                  都得到 context.path == "services.api"）。
        return cls(config)
```

`GPConfigurableContext` 是一个 frozen、slotted 的值对象，只有两个字段：

| 字段      | 含义                                                                                |
|-----------|-------------------------------------------------------------------------------------|
| `manager` | 接收本次 `get_object()` 请求的 `GPConfigManager`。                                  |
| `path`    | 源 YAML 文件的规范点路径（不含 `.yaml`，不含项目名前缀）。                          |

### 示例：引用另一份配置

一个需要数据库配置的 `Worker`。它通过 `context.manager.get_config(...)` 读取数据库
配置的**数据**，而不会构造 `Database` 对象：

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

**YAML 文件：**

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

### 在钩子中选择 `get_config` 还是 `get_object`

钩子里对 manager 的两种调用行为差别很大：

| 调用                                    | 会调用 `from_config` 吗 | 会递归吗 | 是否缓存                          |
|-----------------------------------------|:-----------------------:|:--------:|-----------------------------------|
| `context.manager.get_config(path, Cfg)` | 否                      | 否       | 是——配置数据，按文件缓存          |
| `context.manager.get_object(path)`      | 是                      | 是       | 否——每次调用都返回新对象          |

需要读取另一份配置的**数据**时用 `get_config`。只有需要另一个完整构造的**对象**时才用
`get_object`（并接受它会递归走它自己的 `from_config`）。

### 重要约束

- 钩子**必须**返回已注册可配置类的实例（也允许返回其子类的实例）。其它返回值会触发
  `ConfigurableConstructionError`。
- 钩子抛出的异常——包括签名不兼容导致的 `TypeError`——会原样传播。钩子失败后 manager
  绝不会回退重试旧式 `cls(config)` 构造器。
- `get_object()` **不**缓存对象；每次调用都返回新实例。`get_config()` **会**按文件缓存配置数据。
- **循环引用的检测由调用方负责。** manager 不做循环检测，也不限制深度。如果
  `get_object("a")` 的钩子调 `get_object("b")`，而 `get_object("b")` 的钩子又调回
  `get_object("a")`，就会无限递归直到栈溢出。

> 默认的 `from_config()` 保持了标准子类的契约，因此大多数用户无需重写它。

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
class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:  # 具体类型
        super().__init__(config)
        self.host = config.host  # IDE 可以自动补全
```
