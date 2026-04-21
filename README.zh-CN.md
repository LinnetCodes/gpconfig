# gpconfig

简体中文 | [English](README.md)

通用的 Python 项目配置管理库。

基于 Pydantic 构建的类型安全、YAML 格式的配置管理库。

## 特性

- **类型安全** - 基于 Pydantic，提供完整的类型验证
- **YAML 格式** - 人类可读的配置文件
- **嵌套配置** - 支持目录组织配置（如 `llm/openai.yaml`）
- **自动检测** - 从 YAML 文件自动检测配置类
- **可配置对象** - 直接从配置创建对象实例
- **环境变量支持** - 通过环境变量配置路径
- **只读配置** - 保护敏感配置不被修改

## 安装

```bash
pip install gpconfig
```

## 快速开始

### 1. 定义配置类

```python
from typing import ClassVar
from gpconfig import GPConfig

class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432
    username: str
    password: str
    database: str
```

### 2. 创建配置文件夹

```
myapp/
├── global_env.yaml    # 必需：全局环境配置
├── database.yaml      # 你的配置文件
└── llm/               # 嵌套配置
    ├── openai.yaml
    └── anthropic.yaml
```

**global_env.yaml:**
```yaml
version: "1.0.0"
debug: true
log_level: INFO
```

**database.yaml:**
```yaml
cfg_class_name: "DatabaseConfig"
host: localhost
port: 5432
username: admin
password: secret
database: myapp
```

### 3. 初始化管理器并加载配置

```python
from gpconfig import GPConfigManager

# 配置文件夹搜索顺序：
# 1. 显式指定的 cfg_folder 参数
# 2. 环境变量：{PROJECT_NAME}_CFG_PATH
# 3. 用户目录：~/.{project_name}/
manager = GPConfigManager("myapp", cfg_folder="/path/to/myapp")

# 读取 global_env 中的值
debug = manager.get_config("global_env.debug")

# 加载配置（通过 cfg_class_name 自动检测类）
db_config = manager.get_config("database")

# 加载嵌套配置
llm_config = manager.get_config("llm.openai")

# 读取特定字段
host = manager.get_config("database.host")
```

### 4. 创建可配置对象

```python
from gpconfig import GPConfigurable

class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        self.database = config.database

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

# 注册类
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_configurable_class(Database)

# 创建对象实例
db = manager.get_object("database")
print(db.connection_string)
```

**注意：** 在 YAML 中添加 `configured_class_name` 以使用 `get_object()`：

```yaml
cfg_class_name: "DatabaseConfig"
configured_class_name: "Database"
host: localhost
port: 5432
```

### 5. 保存配置

```python
# 修改并保存
db_config.port = 5433
db_config.save()

# 保存到新位置
manager.save(db_config, "backups/database_backup")
```

## 核心组件

| 组件 | 说明 |
|------|------|
| `GPConfig` | 所有配置类的基类 |
| `GPConfigurable` | 从配置创建的对象的基类 |
| `GPConfigManager` | 管理配置文件夹、加载和对象创建 |

## 异常

| 异常 | 说明 |
|------|------|
| `GPConfigError` | 所有 gpconfig 异常的基类 |
| `ConfigFolderError` | 配置文件夹未找到或无效 |
| `ConfigNotFoundError` | 请求的配置路径不存在 |
| `ConfigReadonlyError` | 尝试修改只读配置 |
| `RegistrationError` | 类注册问题 |
| `ConfigValidationError` | 配置文件验证失败 |

## API 参考

详细用法请参阅 [API 文档](docs/zh/index.md)。

## 许可证

MIT
