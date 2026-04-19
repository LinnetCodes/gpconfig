# 异常类

gpconfig 定义了一组自定义异常类，用于处理配置管理过程中的各种错误情况。

## 导入

```python
from gpconfig import (
    GPConfigError,
    ConfigFolderError,
    ConfigNotFoundError,
    ConfigReadonlyError,
    RegistrationError,
    ConfigValidationError,
)
```

## 异常层次

```
GPConfigError (基类)
├── ConfigFolderError
├── ConfigNotFoundError
├── ConfigReadonlyError
├── RegistrationError
└── ConfigValidationError
```

## GPConfigError

所有 gpconfig 异常的基类。

```python
class GPConfigError(Exception):
    """Base exception for all gpconfig errors."""
    pass
```

### 用法

捕获所有 gpconfig 相关异常：

```python
from gpconfig import GPConfigError, GPConfigManager

try:
    manager = GPConfigManager("myapp")
    config = manager.get_config("database")
except GPConfigError as e:
    print(f"配置错误: {e}")
```

## ConfigFolderError

配置文件夹未找到或无效时抛出。

```python
class ConfigFolderError(GPConfigError):
    """Raised when the config folder cannot be found or is invalid."""
    pass
```

### 触发场景

- 配置文件夹不存在
- 配置路径不是目录
- 配置文件夹缺少 `global_env.yaml`

### 示例

```python
from gpconfig import GPConfigManager, ConfigFolderError
from pathlib import Path

try:
    # 文件夹不存在
    manager = GPConfigManager("myapp", cfg_folder=Path("/nonexistent"))
except ConfigFolderError as e:
    print(f"配置文件夹错误: {e}")
    # 输出: Config folder does not exist: /nonexistent (from explicit parameter)

try:
    # 缺少 global_env.yaml
    manager = GPConfigManager("myapp", cfg_folder=Path("/tmp"))
except ConfigFolderError as e:
    print(f"配置文件夹错误: {e}")
    # 输出: Config folder must contain global_env.yaml: /tmp (from explicit parameter)
```

## ConfigNotFoundError

请求的配置路径不存在时抛出。

```python
class ConfigNotFoundError(GPConfigError):
    """Raised when a requested config path doesn't exist."""

    def __init__(self, path: str, message: str = ""):
        self.path = path
        super().__init__(message or f"Config not found: {path}")
```

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 未找到的配置路径 |

### 触发场景

- 配置文件不存在
- 配置键路径不存在
- 文件夹不存在

### 示例

```python
from gpconfig import GPConfigManager, ConfigNotFoundError

manager = GPConfigManager("myapp")

try:
    config = manager.get_config("nonexistent")
except ConfigNotFoundError as e:
    print(f"未找到配置: {e.path}")
    print(f"错误信息: {e}")

try:
    value = manager.get_config("database.nonexistent_key")
except ConfigNotFoundError as e:
    print(f"未找到键: {e.path}")
```

## ConfigReadonlyError

尝试保存只读配置时抛出。

```python
class ConfigReadonlyError(GPConfigError):
    """Raised when trying to modify or save a readonly config."""

    def __init__(self, config_name: str):
        super().__init__(f"Config '{config_name}' is readonly and cannot be modified")
```

### 触发场景

- 对 `readonly=True` 的配置调用 `save()`

### 示例

```python
from gpconfig import GPConfig, GPConfigManager, ConfigReadonlyError
from typing import ClassVar

class SecureConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "SecureConfig"
    api_key: str

# 获取配置
manager = GPConfigManager("myapp")
config = manager.get_config("secure", SecureConfig)

# 设置为只读
config.readonly = True

try:
    config.api_key = "new_key"
    config.save()
except ConfigReadonlyError as e:
    print(f"无法保存只读配置: {e}")
    # 输出: Config 'secure' is readonly and cannot be modified
```

### 使用场景

只读配置适用于：
- 生产环境敏感配置
- 不应被修改的系统配置
- 防止意外覆盖

```python
# 在生产环境中自动设置只读
import os

config = manager.get_config("production_db", DatabaseConfig)
if os.environ.get("ENV") == "production":
    config.readonly = True
```

## RegistrationError

类注册相关问题时抛出。

```python
class RegistrationError(GPConfigError):
    """Raised when there's an issue with class registration."""
    pass
```

### 触发场景

- 注册重复的 `cfg_class_name`
- 配置类未注册但调用了 `get_object()`
- 配置类没有关联的 `configured_class`

### 示例

```python
from gpconfig import GPConfig, GPConfigManager, RegistrationError
from typing import ClassVar

class MyConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "MyConfig"
    value: str

# 第一次注册 - 成功
GPConfigManager.register_config_class(MyConfig)

# 第二次注册 - 失败
try:
    GPConfigManager.register_config_class(MyConfig)
except RegistrationError as e:
    print(f"注册错误: {e}")
    # 输出: Config class name 'MyConfig' is already registered
```

```python
# 调用 get_object() 但未注册
try:
    obj = manager.get_object("some_config")
except RegistrationError as e:
    print(f"错误: {e}")
    # 输出: Config at path 'some_config' was loaded as dict (no registered config class)
```

```python
# 配置类没有 configured_class_name
GPConfigManager.register_config_class(MyConfig)  # 只注册配置类
# 但配置文件中缺少 configured_class_name 字段

try:
    obj = manager.get_object("my_config")
except RegistrationError as e:
    print(f"错误: {e}")
    # 输出: No configured_class_name found in config at path 'my_config'
```

## ConfigValidationError

配置文件验证失败时抛出。

```python
class ConfigValidationError(GPConfigError):
    """Raised when a config file fails validation."""

    def __init__(self, path: str, original_error: Exception):
        self.path = path
        self.original_error = original_error
        super().__init__(f"Validation failed for '{path}': {original_error}")
```

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 验证失败的配置路径 |
| `original_error` | `Exception` | 原始的 Pydantic 验证错误 |

### 触发场景

- 配置文件内容与配置类类型不匹配
- 缺少必需字段
- 字段类型转换失败

### 示例

```python
from gpconfig import GPConfig, GPConfigManager, ConfigValidationError
from typing import ClassVar

class ServerConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "ServerConfig"
    host: str      # 必需
    port: int      # 必须是整数

# 假设 server.yaml 内容为:
# host: localhost
# port: "not_a_number"  # 类型错误

manager = GPConfigManager("myapp")

try:
    config = manager.get_config("server", ServerConfig)
except ConfigValidationError as e:
    print(f"配置验证失败: {e.path}")
    print(f"原始错误: {e.original_error}")
```

```python
# 缺少必需字段
# 假设 server.yaml 内容为:
# port: 8080
# 缺少 host 字段

try:
    config = manager.get_config("server", ServerConfig)
except ConfigValidationError as e:
    print(f"缺少必需字段: {e}")
```

## 完整异常处理示例

```python
from gpconfig import (
    GPConfig,
    GPConfigurable,
    GPConfigManager,
    GPConfigError,
    ConfigFolderError,
    ConfigNotFoundError,
    ConfigReadonlyError,
    RegistrationError,
    ConfigValidationError,
)
from typing import ClassVar

class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432

class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port

def get_database():
    """获取数据库连接，包含完整的错误处理"""
    try:
        manager = GPConfigManager("myapp")
        # 分别注册配置类和可配置类
        GPConfigManager.register_config_class(DatabaseConfig)
        GPConfigManager.register_configurable_class(Database)
        return manager.get_object("database")

    except ConfigFolderError as e:
        print(f"配置文件夹问题: {e}")
        print("请确保配置文件夹存在并包含 global_env.yaml")
        return None

    except ConfigNotFoundError as e:
        print(f"配置未找到: {e.path}")
        print("请检查配置文件是否存在")
        return None

    except ConfigValidationError as e:
        print(f"配置验证失败: {e.path}")
        print(f"详细信息: {e.original_error}")
        return None

    except RegistrationError as e:
        print(f"注册错误: {e}")
        print("请确保正确注册了配置类和可配置类")
        return None

    except ConfigReadonlyError as e:
        print(f"只读配置: {e}")
        return None

    except GPConfigError as e:
        # 捕获所有其他 gpconfig 异常
        print(f"配置错误: {e}")
        return None

# 使用
db = get_database()
if db:
    print(f"已连接到 {db.host}:{db.port}")
```

**配置文件示例 (database.yaml)：**

```yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
```

## 最佳实践

1. **使用特定的异常类型**：根据具体场景捕获特定的异常
2. **提供有用的错误信息**：在异常处理中提供用户友好的错误信息
3. **记录原始错误**：对于 `ConfigValidationError`，记录 `original_error` 以便调试
4. **使用基类作为兜底**：最后使用 `GPConfigError` 捕获所有未处理的配置异常
