# 异常类

gpconfig 定义了一组自定义异常类，用于处理配置管理过程中的各种错误情况。

## 导入

```python
from gpconfig import (
    GPConfigError,
    ConfigFolderError,
    ConfigNotFoundError,
    IllegalPathError,
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
├── IllegalPathError
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

## IllegalPathError

配置路径格式错误或逃逸出 `cfg_folder`（纵深防御 containment）时抛出。

```python
class IllegalPathError(GPConfigError):
    """Raised when a config path is malformed or escapes the cfg_folder."""

    def __init__(self, path: str, message: str = ""):
        self.path = path
        super().__init__(message or f"Illegal config path: {path}")
```

### 触发场景

当路径满足以下任一条件时被视为格式错误并抛出 `IllegalPathError`：

- **为空** —— 例如 `""`（以前被当作引用根文件夹的可容忍方式）。
- **仅由点组成** —— 例如 `"."`、`".."`。
- **包含连续的点** —— 例如 `"a..b"`。
- **以点开头或结尾** —— 例如 `".x"`、`"x."`（以点结尾以前会因 bug 而返回整个 `global_env` 字典）。
- **在 cfg_path 风格中包含字面量 `/` 或 `\`** —— cfg_path 使用点号表示法；出现原始分隔符即表示路径格式错误。

此外，即使语法上合法，如果路径**解析后位于 `cfg_folder` 之外**，也会抛出 `IllegalPathError`。该 containment 检查是一项纵深防御保证，确保没有任何路径能逃逸出受管文件夹。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 被拒绝的违规路径字符串 |

### 抛出位置

当 `GPConfigManager.get_config()`、`get_object()`、`list_configs()` 和 `save()` 遇到格式错误或逃逸的路径时，都会抛出 `IllegalPathError`。

### 示例

```python
from gpconfig import GPConfigManager, IllegalPathError

manager = GPConfigManager("myapp")

# 格式错误的路径
for bad in ["", ".", "a..b", ".hidden", "global_env.", "a/b"]:
    try:
        manager.get_config(bad)
    except IllegalPathError as e:
        print(f"拒绝 {bad!r}: {e.path} -> {e}")

# save() 拒绝包含 '.' 的路径（cfg_path 风格、'.yaml' 后缀、'..' 穿越）
try:
    manager.save(config, "backups/database.yaml")  # 包含 '.'（.yaml 后缀）
except IllegalPathError as e:
    print(f"保存被拒绝: {e}")
```

## ConfigReadonlyError

尝试保存只读配置时抛出。

```python
class ConfigReadonlyError(GPConfigError):
    """Raised when trying to modify or save a readonly config."""

    def __init__(self, config_name: str):
        super().__init__(f"Config '{config_name}' is readonly and cannot be modified")
```

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

- 用**不同的类**注册一个已被占用的 `cfg_class_name`（重新注册同一个类是幂等的，会静默成功）
- 配置类未注册但调用了 `get_object()`
- 配置类没有关联的 `configured_class`

### 示例

```python
from gpconfig import GPConfig, GPConfigManager, RegistrationError
from typing import ClassVar

class MyConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "MyConfig"
    value: str

class ConflictConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "MyConfig"  # 相同的 cfg_class_name，不同的类
    other: str

# 第一次注册 - 成功
GPConfigManager.register_config_class(MyConfig)

# 用不同的类在相同名字下再次注册 - 失败
try:
    GPConfigManager.register_config_class(ConflictConfig)
except RegistrationError as e:
    print(f"注册错误: {e}")
    # 输出: Config class name 'MyConfig' is already registered with a different class
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

### 触发条件

当配置文件无法被转成合法的配置对象时，`GPConfigManager.get_config()`（及其 YAML 加载路径）会抛出 `ConfigValidationError`：

- **YAML 语法/解析错误** —— 畸形 YAML（缩进错误、引号/括号未闭合、使用了 Tab 等）。原始错误为 `yaml.YAMLError`，其消息带有文件路径、行号和列号（例如 `in ".../server.yaml", line 3, column 5`）。
- **顶层非字典** —— YAML 能解析，但根节点是列表或标量而非映射。消息中嵌入磁盘上的文件路径。
- **Pydantic 校验失败** —— YAML 解析成字典，但某字段未通过 schema 校验（类型错误、缺少必填字段、或在 `extra="forbid"` 下出现多余字段）。原始错误为 Pydantic 的 `ValidationError`，其消息会指出出错的字段名。

无论哪种情况，异常消息都携带**点分配置路径**（`.path`）、**磁盘上的文件路径**，以及底层错误的细节（字段名和/或行号），方便你精确定位问题。

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 验证失败的点分配置路径 |
| `original_error` | `Exception` | 底层错误：Pydantic 的 `ValidationError`、`yaml.YAMLError`，或 `TypeError`（顶层非字典） |

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
    # e.path 是点分配置路径，例如 "server"。
    # str(e) 同时会嵌入磁盘上的文件路径和出错字段名。
    print(f"原始错误: {e.original_error}")
```

## 最佳实践

1. **使用特定的异常类型**：根据具体场景捕获特定的异常
2. **提供有用的错误信息**：在异常处理中提供用户友好的错误信息
3. **记录原始错误**：对于 `ConfigValidationError`，记录 `original_error` 以便调试
4. **使用基类作为兜底**：最后使用 `GPConfigError` 捕获所有未处理的配置异常
