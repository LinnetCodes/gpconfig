# GPConfig 类

`GPConfig` 是所有配置类的基类，基于 Pydantic 的 `BaseSettings` 构建，提供类型安全的配置管理。

## 导入

```python
from gpconfig import GPConfig
```

## 类定义

```python
class GPConfig(BaseSettings):
    # 类级变量
    cfg_class_name: ClassVar[str] = "GPConfig"
    default_cfg_path: ClassVar[Optional[str]] = None

    # 实例字段
    name: str = ""
    cfg_file_path: Path = Path()
    readonly: bool = False
    configured_class_name: Optional[str] = None
```

## 类级变量

### cfg_class_name

用于自动检测配置类的标识符。在 YAML 文件中设置此值可以自动关联配置类。

```python
from typing import ClassVar
from gpconfig import GPConfig

class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432
```

对应的 YAML 文件：

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
host: localhost
port: 5432
```

### configured_class_name (实例字段)

与此配置类关联的可配置对象类的名称。此字段存储在 YAML 文件中，用于 `get_object()` 自动查找对应的可配置类。

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
```

```python
from gpconfig import GPConfig, GPConfigManager
from typing import ClassVar

class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432

# 注册配置类和可配置类
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_configurable_class(Database)

# 配置加载时，configured_class_name 用于查找对应的可配置类
manager = GPConfigManager("myapp")
db = manager.get_object("database")  # 自动使用 Database 类
```

### default_cfg_path

保存配置时的默认相对路径。

```python
class CacheConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "CacheConfig"
    default_cfg_path: ClassVar[str] = "cache"  # 保存到 cache/{name}.yaml
    host: str = "localhost"
```

## 实例字段

### name

配置名称，通常设置为 YAML 文件的文件名（不含扩展名）。

```python
config = DatabaseConfig(host="localhost")
config.name = "production"
```

### cfg_file_path

配置文件的完整路径。

```python
config.cfg_file_path = Path("/etc/myapp/database.yaml")
```

### readonly

是否为只读配置。设为 `True` 时调用 `save()` 会抛出异常。

```python
config = DatabaseConfig(host="localhost", readonly=True)
config.save()  # 抛出 ConfigReadonlyError
```

## 方法

### save()

将当前配置状态保存回 YAML 文件。

```python
def save(self) -> None:
    """Save current config state back to the YAML file.

    Raises:
        ConfigReadonlyError: If readonly is True
    """
```

**示例：**

```python
from typing import ClassVar
from gpconfig import GPConfig, GPConfigManager

class ServerConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "ServerConfig"
    host: str = "localhost"
    port: int = 8080

# 初始化管理器
manager = GPConfigManager("myapp")

# 获取配置
config = manager.get_config("server", ServerConfig)

# 修改配置
config.port = 9000

# 保存到文件
config.save()
```

**注意事项：**

- `save()` 会排除 `name`、`cfg_file_path` 和 `readonly` 字段
- `cfg_class_name` 会被包含在保存的 YAML 中
- `configured_class_name` 如果设置了，也会被包含在保存的 YAML 中
- 配置必须是可写的（`readonly=False`）

## 类型验证

GPConfig 继承自 Pydantic，支持完整的类型验证：

```python
from typing import ClassVar, List
from gpconfig import GPConfig

class AppConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "AppConfig"

    # 必需字段
    app_name: str

    # 带默认值
    debug: bool = False

    # 各种类型
    port: int = 8080
    timeout: float = 30.0
    allowed_hosts: List[str] = []

# 验证失败示例
from pydantic import ValidationError

try:
    config = AppConfig(app_name="MyApp", port="invalid")
except ValidationError as e:
    print(f"验证失败: {e}")
```

## 禁止额外字段

默认配置下，GPConfig 不允许未定义的字段：

```python
class StrictConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "StrictConfig"
    name: str

# 这会抛出 ValidationError
config = StrictConfig(name="test", unknown_field="value")
```

## 完整示例

### 定义和使用配置类

```python
from typing import ClassVar
from pathlib import Path
from gpconfig import GPConfig, GPConfigManager

# 定义配置类
class DatabaseConfig(GPConfig):
    """数据库连接配置"""
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    default_cfg_path: ClassVar[str] = "databases"  # 保存到 databases/ 目录

    host: str
    port: int = 5432
    username: str
    password: str
    database: str
    pool_size: int = 10

# 初始化管理器
manager = GPConfigManager("myapp")

# 注册配置类
GPConfigManager.register_config_class(DatabaseConfig)

# 获取配置
config = manager.get_config("databases.primary")

print(f"Host: {config.host}")
print(f"Port: {config.port}")
print(f"Database: {config.database}")

# 修改并保存
config.pool_size = 20
config.save()

# 使用管理器保存到新位置
new_config = DatabaseConfig(
    host="localhost",
    username="admin",
    password="secret",
    database="test_db"
)
new_config.name = "test"
manager.save(new_config)  # 保存到 databases/test.yaml
```

### 只读配置

```python
# 创建只读配置（通常用于生产环境敏感配置）
config = manager.get_config("production_db")
config.readonly = True

# 尝试保存会抛出异常
config.port = 5433
config.save()  # ConfigReadonlyError!
```
