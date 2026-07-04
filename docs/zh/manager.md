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

> **约束：project_name 不能与配置子目录名冲突。**
>
> 如果 `cfg_folder` 包含一个与 `project_name` 同名的顶层子目录，`GPConfigManager.__init__`
> 会抛出 `ConfigFolderError`。这是因为可选的 `project_name` 路径前缀（例如
> `get_config("myapp.x")`）会遮蔽该子目录，使其无法通过点号表示法访问。该检查在构造时
> 执行一次（只扫描一层；空子目录也会触发）。如果遇到此错误，请重命名项目名或子目录。

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

以**只读**的 `MappingProxyType` 视图（而非可变 `dict`）获取全局环境配置。

```python
# global_env.yaml 内容:
# version: "1.0.0"
# debug: true

print(manager.global_env["version"])  # "1.0.0"
print(manager.global_env["debug"])    # True
```

**只读 —— 不允许修改。** 返回的视图用于保护 manager 的内部状态，并与缓存的快照模型保持一致（参见[配置缓存与失效](#配置缓存与失效)）。任何修改尝试都会抛出异常：

```python
manager.global_env["new_key"] = "value"  # TypeError: 'mappingproxy' object does not support item assignment
del manager.global_env["debug"]          # TypeError: 'mappingproxy' object does not support item deletion
manager.global_env.pop("debug")          # AttributeError: 'mappingproxy' object has no attribute 'pop'
manager.global_env.update({"x": 1})      # AttributeError: 'mappingproxy' object has no attribute 'update'
```

项操作（`[k] = v`、`del`）抛出 `TypeError`；缺失的可变方法（`.pop()`、`.update()`）抛出 `AttributeError`。

如需可变副本，请将其物化为普通 dict：

```python
env = dict(manager.global_env)  # 一个可以自由修改的普通 dict
env["new_key"] = "value"
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

**抛出：**
- 当路径格式错误或逃逸出 `cfg_folder` 时抛出 `IllegalPathError`。
- 当格式正确的路径无法解析到已存在的文件或键时抛出 `ConfigNotFoundError`。

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

> ⚠️ **明文存储 —— 敏感信息请自行加密。**
>
> `gpconfig` 将所有配置值以**明文**写入 YAML 文件，包括密码、API Key、令牌等字段。本库**不**提供加密、脱敏或 `SecretStr` 处理 —— 这是有意为之的设计，因为依赖 YAML 配置库来保护密钥并不能替代真正的密钥管理方案。
>
> 如果需要存储敏感信息：
> - 在放入配置文件之前**自行加密**（例如使用来自密钥管理服务、环境变量或 KMS 的密钥），并在应用代码中于 `gpconfig` 加载后解密。
> - 或者**完全不将密钥写入配置文件**，改用环境变量或专用密钥存储注入。
>
> 作为基本防护，请限制 `cfg_folder` 的文件权限，但不要将明文配置文件视为安全的密钥存储。

```python
def save(self, config: "GPConfig", path: Optional[str] = None) -> None:
    """Save a GPConfig instance to a config file."""
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `GPConfig` | 要保存的配置实例 |
| `path` | `str \| None` | 可选的相对文件夹路径（文件系统风格，以 `/` 或 `\` 分隔）。文件始终命名为 `{config.name}.yaml` 并位于该文件夹内。不能包含 `.`。 |

**抛出：**
- 当路径格式错误或逃逸出 `cfg_folder` 时抛出 `IllegalPathError`（例如包含 `.`，包括 cfg_path 风格、`.yaml` 后缀或 `..` 穿越）。
- 当配置设置了 `readonly=True` 时抛出 `ConfigReadonlyError`。

**示例：**

```python
# 获取并修改配置
config = manager.get_config("database", DatabaseConfig)
config.port = 5433

# 保存（使用原有路径）
manager.save(config)

# 保存到新文件夹（文件系统风格；'.' 会被拒绝）
manager.save(config, "backups/database_backup")  # IllegalPathError: 包含 '.'
manager.save(config, "backups/db_backups")       # OK -> backups/db_backups/{config.name}.yaml

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

### invalidate_cache()

使内存中的配置缓存失效，强制下一次 `get_config` 调用重新从磁盘读取。

```python
def invalidate_cache(self, path: Optional[str] = None) -> None:
    """使配置缓存失效。"""
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `path` | `str \| None` | 可选的点分配置路径，指定要失效的文件。如果为 None，则清空整个缓存。 |

**示例：**

```python
# 清空整个缓存（下一次 get_config 会全部重新加载）
manager.invalidate_cache()

# 清除单个文件的缓存条目
manager.invalidate_cache("database")

# 格式正确但无法解析到文件的路径是空操作（不报错）
manager.invalidate_cache("does.not.exist")
```

**注意：** 格式错误的路径会抛出 `IllegalPathError`；只有格式正确但文件不存在的路径会被静默忽略。

## 配置缓存与失效

`GPConfigManager` 在内存中缓存配置对象，缓存的生命周期与该 manager 实例一致。一旦通过 `get_config` 加载了配置文件，后续调用会直接返回缓存的对象，而不会重新从磁盘读取。这适用于**整对象访问**（`get_config("database")`）和键路径访问（`get_config("database.port")`）——两者都会填充缓存。

这是一种**快照（snapshot）**模型：内存中的缓存不会自动检测配置文件的外部更改。

当你通过 `GPConfigManager.save()`（或 `GPConfig.save()`）保存配置时，缓存会自动更新以反映已保存的对象。但是，如果配置文件被其他方式修改（手动编辑、其他进程或工具写入），manager 会继续返回过期的缓存值。

要在被外部修改后强制重新加载，请调用 `manager.invalidate_cache()`（清空整个缓存）或 `manager.invalidate_cache(path)`（清除单个文件的缓存条目）。下一次 `get_config` 调用会重新从磁盘读取。

```python
# 第一次访问时填充缓存
config = manager.get_config("database")  # 读取磁盘并缓存

# 后续调用命中缓存（无磁盘 I/O）
config2 = manager.get_config("database")  # 命中缓存
assert config is config2

# 在缓存失效之前，外部修改不会被看到
manager.invalidate_cache()
config3 = manager.get_config("database")  # 再次读取磁盘
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
