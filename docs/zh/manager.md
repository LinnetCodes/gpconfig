# GPConfigManager 类

`GPConfigManager` 是配置管理的核心类，负责配置文件夹解析、配置加载、类注册和对象创建。

## 导入

```python
from gpconfig import GPConfigManager
```

## 类定义

```python
class GPConfigManager:
    # 类级注册表
    _config_classes: dict[str, Type[Any]] = {}
    _configurable_classes: dict[str, Type[Any]] = {}

    def __init__(self, project_name: str, cfg_folder: Optional[Path | str] = None):
        """初始化配置管理器"""
```

## 初始化

### 构造函数参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `project_name` | `str` | 项目名称，用于环境变量和目录命名 |
| `cfg_folder` | `Path \| str \| None` | 可选的配置文件夹路径 |

### 配置文件夹搜索规则

按以下顺序搜索配置文件夹：

1. **显式参数** - `cfg_folder` 参数
2. **环境变量** - `{PROJECT_NAME}_CFG_PATH`（大写）
3. **用户目录** - `~/.{project_name}/`

### 示例

```python
from pathlib import Path
from gpconfig import GPConfigManager

# 方式 1：显式指定路径
manager = GPConfigManager("myapp", cfg_folder=Path("/etc/myapp"))

# 方式 2：使用环境变量 MYAPP_CFG_PATH
# export MYAPP_CFG_PATH=/path/to/configs
manager = GPConfigManager("myapp")

# 方式 3：使用用户目录
# 配置文件夹: ~/.myapp/
manager = GPConfigManager("myapp")
```

### 配置文件夹要求

有效的配置文件夹必须：
- 存在且为目录
- 包含 `global_env.yaml` 文件

```
myapp/
├── global_env.yaml    # 必需
├── database.yaml
└── llm/
    └── openai.yaml
```

## 属性

### project_name

获取项目名称。

```python
manager = GPConfigManager("myapp")
print(manager.project_name)  # "myapp"
```

### cfg_folder

获取配置文件夹的完整路径。

```python
print(manager.cfg_folder)  # Path("/path/to/configs")
```

### global_env

获取全局环境配置字典。

```python
# global_env.yaml 内容:
# version: "1.0.0"
# debug: true

print(manager.global_env["version"])  # "1.0.0"
print(manager.global_env["debug"])    # True
```

## 类方法

### register_config_class()

注册配置类（不含可配置对象映射）。

```python
@classmethod
def register_config_class(cls, config_cls: Type[Any]) -> None:
    """Register a config class by its cfg_class_name."""
```

**示例：**

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigManager

class AppConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "AppConfig"
    debug: bool = False

# 注册配置类
GPConfigManager.register_config_class(AppConfig)

# 现在可以自动检测并加载
manager = GPConfigManager("myapp")
config = manager.get_config("app")  # 自动使用 AppConfig 类
```

### register_configurable_class()

注册可配置对象类。只需要传入可配置类本身，系统会通过类名进行查找。

```python
@classmethod
def register_configurable_class(
    cls,
    configurable_cls: Type[Any]
) -> None:
    """Register a configurable class by its class name."""
```

**示例：**

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

# 注册配置类
GPConfigManager.register_config_class(DatabaseConfig)

# 注册可配置类（只需传入类本身）
GPConfigManager.register_configurable_class(Database)
```

**YAML 配置文件：**

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
```

当调用 `get_object("database")` 时，系统会：
1. 加载配置，读取 `cfg_class_name` 和 `configured_class_name`
2. 通过 `configured_class_name` 在 `_configurable_classes` 中查找对应的类
3. 使用找到的类创建对象实例

### make_new_project_config_folder()

创建新的项目配置文件夹。

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

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `project_name` | `str` | 项目名称 |
| `cfgs` | `List[GPConfig]` | GPConfig 实例列表，每个必须有 `name` |
| `global_env` | `dict \| None` | global_env.yaml 的内容 |
| `cfg_folder_path` | `str \| Path \| None` | 可选的配置文件夹路径 |

**返回值：** 创建的配置文件夹路径

**示例：**

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

# 创建配置实例
db_config = DatabaseConfig()
db_config.name = "database"

cache_config = CacheConfig()
cache_config.name = "redis"

# 创建项目配置文件夹
folder = GPConfigManager.make_new_project_config_folder(
    project_name="myapp",
    cfgs=[db_config, cache_config],
    global_env={"version": "1.0.0", "debug": True}
)

# 结果:
# ~/.myapp/
# ├── global_env.yaml
# ├── database.yaml
# └── cache/
#     └── redis.yaml
```

**路径解析规则：**

1. 显式参数 `cfg_folder_path`
2. 环境变量 `{PROJECT_NAME}_CFG_PATH`
3. 用户主目录 `~/.{project_name}/`

**异常：**

| 异常 | 触发条件 |
|------|----------|
| `ConfigFolderError` | 配置文件夹已存在 |
| `ValueError` | 配置的 `name` 为空 |
| `ConfigReadonlyError` | 配置设置了 `readonly=True` |

## 实例方法

### get_config()

获取配置对象或配置值。

```python
def get_config(
    self,
    path: str,
    config_cls: Optional[Type[T]] = None
) -> Union[T, Any]:
    """Get a config object or a specific config value."""
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 配置路径，支持点号分隔 |
| `config_cls` | `Type[T] \| None` | 可选的配置类 |

**返回值：**
- 如果 `config_cls` 指定或自动检测到，返回配置对象实例
- 如果路径指向特定键，返回该键的值
- 否则返回原始字典

**示例：**

```python
# 读取 global_env 中的值
debug = manager.get_config("global_env.debug")
version = manager.get_config("global_env.version")

# 读取整个配置文件（自动检测类）
config = manager.get_config("database")

# 读取配置文件（指定类）
config = manager.get_config("database", DatabaseConfig)

# 读取嵌套配置
config = manager.get_config("llm.openai", LLMConfig)

# 读取配置中的特定值
host = manager.get_config("database.host")
model = manager.get_config("llm.anthropic.model")
```

### get_object()

从配置路径获取可配置对象实例。系统会从配置实例的 `configured_class_name` 字段读取要使用的类名，然后在注册表中查找对应的类。

```python
def get_object(self, path: str) -> Any:
    """Get a configurable object instance from a config path."""
```

**示例：**

```python
# 注册配置类和可配置类
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_configurable_class(Database)

# 创建对象 - 配置文件中需要有 configured_class_name: "Database"
db = manager.get_object("database")
print(db.host)  # 配置中的值

# 嵌套配置
llm = manager.get_object("llm.openai")
```

**配置文件示例：**

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"  # 必须设置此项才能使用 get_object()
host: localhost
port: 5432
```

**注意：**
- 每次调用都创建新实例
- 配置文件必须包含 `configured_class_name` 字段
- `configured_class_name` 对应的类必须已通过 `register_configurable_class()` 注册

### list_configs()

列出文件夹中的所有配置对象。

```python
def list_configs(self, path: str = "") -> list[str]:
    """List all config objects in a folder."""
```

**示例：**

```python
# 列出根目录
items = manager.list_configs()
# ['database', 'llm', 'cache']

# 列出子目录
llm_items = manager.list_configs("llm")
# ['openai', 'anthropic']

# 使用点号分隔
llm_items = manager.list_configs("services.llm")
# ['openai', 'anthropic']
```

### save()

保存配置到文件。

```python
def save(self, config: "GPConfig", path: Optional[str] = None) -> None:
    """Save a GPConfig instance to a config file."""
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `GPConfig` | 要保存的配置实例 |
| `path` | `str \| None` | 可选的相对路径 |

**示例：**

```python
# 获取并修改配置
config = manager.get_config("database", DatabaseConfig)
config.port = 5433

# 保存（使用原有路径）
manager.save(config)

# 保存到新路径
manager.save(config, "backups/database_backup")

# 保存新配置
new_config = DatabaseConfig(
    host="localhost",
    username="admin",
    password="secret",
    database="test"
)
new_config.name = "test"
manager.save(new_config)  # 保存到 default_cfg_path/test.yaml
```

## GPConfigFolder

表示配置文件夹层次结构中的子文件夹。提供对特定文件夹内配置的便捷访问。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 从 cfg_folder 开始的相对路径，使用点号表示法（如 "llm.providers"） |

### 方法

#### `__init__(manager, relative_path)`

初始化 GPConfigFolder。

| 参数 | 类型 | 说明 |
|------|------|------|
| `manager` | `GPConfigManager` | GPConfigManager 实例 |
| `relative_path` | `str` | 从 cfg_folder 开始的相对路径，使用点号表示法 |

#### `get_config(path, config_cls=None)`

从此文件夹获取配置对象或值。

| 参数 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 相对于此文件夹的配置路径 |
| `config_cls` | `Type[T]` | 可选的 GPConfig 子类，用于加载 |

**返回值：** `GPConfig` 实例、`GPConfigFolder` 或配置值。

#### `get_object(path)`

从此文件夹获取可配置对象实例。

| 参数 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 相对于此文件夹的配置路径 |

**返回值：** 配置的 GPConfigurable 子类的新实例。

#### `list_configs()`

列出此文件夹中的所有配置对象。

**返回值：** `List[str]` - 对象名称列表（配置名称和子文件夹名称）。
