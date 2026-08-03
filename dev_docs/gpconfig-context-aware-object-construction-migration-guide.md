# gpconfig 上下文感知对象构造适配指南

## 适用范围

上下文感知对象构造引入两项 breaking change：

1. `GPConfigManager.register_configurable_class()` 只接受 `GPConfigurable` 子类；
2. `GPConfigManager.get_object()` 会调用 `from_config(config, *, context)`。

标准的 `GPConfigurable(config)` 子类无需修改，YAML 也无需增加字段。

## 标准子类无需适配

以下代码继续有效：

```python
class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)

GPConfigManager.register_configurable_class(Database)
database = manager.get_object("database")
```

默认 `GPConfigurable.from_config()` 会调用 `Database(config)`。

## 将 duck-typed 类改为 GPConfigurable 子类

旧代码：

```python
class Database:
    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
```

适配后：

```python
class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
```

未适配的类型会在 `register_configurable_class()` 调用时抛出 `RegistrationError`。

## 处理已有同名 from_config 方法

如果现有 `from_config()` 是其他来源的工厂方法，应将它重命名为表达原来源的方法：

```python
class Database(GPConfigurable):
    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> "Database":
        config = DatabaseConfig.model_validate(data)
        return cls(config)
```

如果该方法就是 gpconfig 对象构造入口，则适配为新签名：

```python
class Portfolio(GPConfigurable):
    @classmethod
    def from_config(
        cls,
        config: PortfolioConfig,
        *,
        context: GPConfigurableContext,
    ) -> "Portfolio":
        return PortfolioResolver(context.manager).resolve(
            context.path,
            root_config=config,
        )
```

`context.manager` 是发起构造的 manager，`context.path` 是不带项目名前缀和 `.yaml` 的规范点路径。

## 返回值和异常契约

- 钩子必须返回已注册 configurable 类或其子类的实例；其他返回值会触发 `ConfigurableConstructionError`。
- 钩子抛出的业务异常和签名错误会原样传播。
- 钩子失败后 gpconfig 不会调用旧式构造器重试。
- `get_object()` 仍然每次创建新对象，不缓存对象。

## 无需迁移的配置内容

以下内容不变：

- `cfg_class_name` 和 `configured_class_name`；
- YAML 文件结构；
- `GPConfig.save()` 输出；
- manager 的配置缓存；
- `GPConfigFolder.get_object()` 的调用方式。
