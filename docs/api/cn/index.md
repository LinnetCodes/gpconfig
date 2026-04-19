# gpconfig API 文档

gpconfig 是一个通用的 Python 配置管理库，基于 Pydantic 构建，提供类型安全的配置管理功能。

## 安装

```bash
pip install gpconfig
```

## 核心组件

| 组件 | 说明 |
|------|------|
| [`GPConfig`](gpconfig.md) | 配置基类，所有配置类都应继承此类 |
| [`GPConfigurable`](configurable.md) | 可配置对象基类，用于从配置创建对象实例 |
| [`GPConfigManager`](manager.md) | 配置管理器，负责配置文件夹解析、配置加载和对象创建 |
| [`GPConfigFolder`](manager.md#gpconfigfolder) | 表示配置文件夹层次结构中的子文件夹 |

## 异常

| 异常 | 说明 |
|------|------|
| `GPConfigError` | 所有 gpconfig 异常的基类 |
| `ConfigFolderError` | 配置文件夹未找到或无效 |
| `ConfigNotFoundError` | 请求的配置路径不存在 |
| `ConfigReadonlyError` | 尝试修改只读配置 |
| `RegistrationError` | 类注册问题 |
| `ConfigValidationError` | 配置文件验证失败 |

详细信息请参阅 [异常文档](exceptions.md)。

## 快速开始

### 1. 定义配置类

```python
from typing import ClassVar
from gpconfig import GPConfig

class DatabaseConfig(GPConfig):
    """数据库配置"""
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432
    username: str
    password: str
    database: str
```

### 2. 创建配置文件夹

在项目根目录或用户目录下创建配置文件夹，包含 `global_env.yaml`：

```
myapp/
├── global_env.yaml    # 全局环境配置（必需）
├── database.yaml      # 数据库配置
└── llm/               # 嵌套配置
    ├── openai.yaml
    └── anthropic.yaml
```

**global_env.yaml 示例：**

```yaml
version: "1.0.0"
debug: true
log_level: INFO
```

**database.yaml 示例：**

```yaml
cfg_class_name: "DatabaseConfig"
host: localhost
port: 5432
username: admin
password: secret
database: myapp
```

### 3. 初始化配置管理器

```python
from pathlib import Path
from gpconfig import GPConfigManager

# 方式 1：指定配置文件夹路径
manager = GPConfigManager("myapp", cfg_folder=Path("/path/to/configs"))

# 方式 2：使用环境变量 MYAPP_CFG_PATH
manager = GPConfigManager("myapp")

# 方式 3：使用用户目录下的 myapp 文件夹 (~/.myapp/)
manager = GPConfigManager("myapp")
```

### 4. 读取配置

```python
# 读取 global_env 中的值
debug = manager.get_config("global_env.debug")
version = manager.get_config("global_env.version")

# 读取配置文件（自动检测 cfg_class_name）
db_config = manager.get_config("database")

# 指定配置类读取
db_config = manager.get_config("database", DatabaseConfig)

# 读取嵌套配置
llm_config = manager.get_config("llm.openai")

# 读取配置中的特定值
host = manager.get_config("database.host")
```

### 5. 定义可配置对象

```python
from gpconfig import GPConfigurable

class Database(GPConfigurable):
    """数据库连接对象"""

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

### 6. 注册并创建对象

```python
# 注册配置类
GPConfigManager.register_config_class(DatabaseConfig)

# 注册可配置类（只需传入类本身）
GPConfigManager.register_configurable_class(Database)

# 从配置创建对象实例
db = manager.get_object("database")
print(db.connection_string)
# 输出: postgresql://admin:secret@localhost:5432/myapp
```

**注意：** 配置文件需要包含 `configured_class_name` 字段：

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

### 7. 保存配置

```python
# 获取配置并修改
db_config = manager.get_config("database", DatabaseConfig)
db_config.port = 5433

# 保存回文件
db_config.save()

# 或者使用管理器保存到新位置
manager.save(db_config, "backups/database_backup")
```

## 配置文件夹搜索规则

GPConfigManager 按以下顺序搜索配置文件夹：

1. **显式参数** - 构造函数的 `cfg_folder` 参数
2. **环境变量** - `{PROJECT_NAME}_CFG_PATH`（大写）
3. **用户目录** - `~/{project_name}/`

有效的配置文件夹必须包含 `global_env.yaml` 文件。

## 类型安全

gpconfig 基于 Pydantic 构建，提供完整的类型验证：

```python
class ServerConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "ServerConfig"
    host: str                    # 必需字段
    port: int = 8080             # 带默认值
    debug: bool = False          # 布尔类型
    timeout: float = 30.0        # 浮点类型

# 类型不匹配会抛出 ConfigValidationError
config = ServerConfig(host="localhost", port="invalid")  # 报错！
```

## 完整示例

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigurable, GPConfigManager

# 1. 定义配置类
class CacheConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "CacheConfig"
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""

# 2. 定义可配置对象
class Cache(GPConfigurable):
    def __init__(self, config: CacheConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port
        self.db = config.db
        self.password = config.password

    def connect(self):
        print(f"Connecting to Redis at {self.host}:{self.port}")

# 3. 初始化管理器
manager = GPConfigManager("myapp")

# 4. 注册类（分别注册配置类和可配置类）
GPConfigManager.register_config_class(CacheConfig)
GPConfigManager.register_configurable_class(Cache)

# 5. 使用配置
cache = manager.get_object("cache")
cache.connect()
```

**cache.yaml 配置文件：**

```yaml
cfg_class_name: "CacheConfig"
configured_class_name: "Cache"
host: localhost
port: 6379
db: 0
password: ""
```
