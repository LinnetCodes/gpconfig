# gpconfig 上下文感知对象构造重构需求

## 状态

- 状态：Draft
- 目标项目：`gpconfig`
- 基于版本：0.3.4
- 实施时间：未来版本，不属于 Quant Types Portfolio v1 的前置需求
- 兼容性目标：保持现有 `GPConfigurable(config)` 子类和 YAML 配置兼容

## 背景

gpconfig 0.3.4 的 `GPConfigManager.get_object(path)` 会先加载对应的
`GPConfig`，再调用已注册 configurable 类的单参数构造器：

```python
return configurable_cls(config)
```

这个契约适合只依赖单个配置文件的对象，但无法干净地支持需要读取配置树中其他配置的对象。
例如 Quant Types 的 `Portfolio` 配置可以引用其他 portfolio 文件。构造完整的
`Portfolio` 时，需要同时知道：

- 发起构造的 `GPConfigManager`；
- 当前配置文件在该 manager 中的规范点路径；
- 当前 manager 的缓存和配置目录语义；
- 后续递归加载使用的同一配置上下文。

仅把根 `PortfolioConfig` 传给 `Portfolio(config)`，无法满足这些要求。

## 问题陈述

`GPConfigurable` 的对象构造缺少显式上下文。下游库若要从构造器读取其他配置，目前只能选择
以下不理想的做法：

- 使用进程级全局 manager；
- 从 `cfg_file_path` 向上扫描配置根目录并创建新 manager；
- 把 manager 动态附加到 `GPConfig`；
- 创建尚未解析完成、需要稍后手动初始化的对象。

这些方案会引入隐藏依赖、重复缓存、半有效对象或无法可靠恢复 `project_name` 的问题。

## 设计目标

1. 允许 configurable 对象在构造期间访问发起调用的 manager 和规范配置路径。
2. 保持 `GPConfig` 为纯配置数据，不强制持有 manager 或提供隐式 I/O 能力。
3. 保持现有只实现 `__init__(config)` 的 `GPConfigurable` 子类兼容。
4. 让 `GPConfigManager.get_object()` 和 `GPConfigFolder.get_object()` 使用相同的构造语义。
5. 保持 `get_object()` 每次创建新对象的现有行为，不增加对象缓存。
6. 对无效构造器返回值和异常执行 Fail-Fast，不回退或重试其他构造路径。

## 非目标

- 不把 `GPConfigManager` 注入每一个 `GPConfig` 实例。
- 不改变 YAML 中 `cfg_class_name` 或 `configured_class_name` 的含义。
- 不为 configurable 对象增加自动刷新、文件监听或惰性重载。
- 不改变 `GPConfigManager.get_config()` 的配置缓存策略。
- 不在 gpconfig 内实现 portfolio 专用的递归、循环或深度校验。

## 建议设计

### 1. 增加不可变构造上下文

新增公开的不可变上下文类型：

```python
@dataclass(frozen=True, slots=True)
class GPConfigurableContext:
    manager: GPConfigManager
    path: str
```

字段语义：

- `manager` 是接收 `get_object()` 调用的原始 manager 实例。
- `path` 是相对于 manager 配置根目录的规范点路径，不含 `.yaml`。
- `path` 必须经过 manager 现有路径规则规范化；可选的项目名前缀不得造成两个不同身份。
- 上下文只负责提供构造依赖，不自动保存到 `GPConfig`。

### 2. 为 GPConfigurable 增加类级构造钩子

新增 `from_config()` 类方法。默认实现继续调用现有单参数构造器：

```python
class GPConfigurable:
    @classmethod
    def from_config(
        cls,
        config: GPConfig,
        *,
        context: GPConfigurableContext,
    ) -> GPConfigurable:
        return cls(config)
```

要求：

- `context` 必须为关键字参数。
- 默认实现不得读取、修改或保存配置。
- 已有子类无需覆盖该方法，也无需修改 `__init__(config)`。
- 需要配置树访问能力的子类可以覆盖该方法。
- 覆盖实现可以在构造完成后丢弃 context，以生成不再依赖 manager 的不可变快照。

实际类型标注应兼容 gpconfig 当前支持的最低 Python 版本；可以使用绑定到
`GPConfigurable` 的 `TypeVar`，不应仅为 `Self` 提高最低 Python 版本。

### 3. 修改 GPConfigManager.get_object()

`get_object(path)` 在完成现有配置加载和 configurable 类查找后：

1. 取得当前 manager 规则下的规范配置路径；
2. 创建 `GPConfigurableContext(manager=self, path=normalized_path)`；
3. 调用 `configurable_cls.from_config(config, context=context)`；
4. 验证返回值是所注册 configurable 类的实例；
5. 返回该对象。

默认钩子必须保证现有行为等价于 `configurable_cls(config)`。

### 4. GPConfigFolder.get_object() 保持代理职责

`GPConfigFolder.get_object(relative_path)` 继续把 folder 路径和相对路径组合成完整点路径，
再调用所属 manager 的 `get_object()`。构造上下文中的 `manager` 必须仍是原始 manager，
`path` 必须是组合并规范化后的完整路径。

### 5. 错误契约

- 未注册配置类、未注册 configurable 类以及缺少 `configured_class_name` 的现有异常保持不变。
- `from_config()` 抛出的业务异常原样传播，不包装、不重试。
- `from_config()` 返回错误类型时立即抛出专门的 configurable 构造契约异常；该异常应属于
  gpconfig 的编程错误类别，而不是配置内容校验错误。
- 不得在钩子失败后回退到 `configurable_cls(config)`，否则会隐藏钩子实现错误。

## Portfolio 集成示例

未来 Quant Types 可以在 YAML 中启用 gpconfig 对象构造：

```yaml
cfg_class_name: PortfolioConfig
configured_class_name: Portfolio
weight_mode: specified
components:
  - portfolio: portfolio.sleeves.equity
    weight: 0.60
  - portfolio: portfolio.sleeves.defensive
    weight: 0.40
```

Portfolio 的上下文构造钩子可以委托给既有 resolver：

```python
@classmethod
def from_config(
    cls,
    config: PortfolioConfig,
    *,
    context: GPConfigurableContext,
) -> Portfolio:
    return PortfolioResolver(context.manager).resolve(
        context.path,
        root_config=config,
    )
```

用户随后可以使用：

```python
portfolio = manager.get_object("portfolio.all_weather")
portfolio = portfolio_folder.get_object("all_weather")
```

resolver 仍然负责 Symbol 解析、引用递归、循环检测、最大深度和权重聚合；gpconfig 只提供
通用构造上下文，不理解 portfolio 领域规则。

## 向后兼容要求

- 现有 `GPConfigurable` 子类仅实现 `__init__(config)` 时，行为不得改变。
- 现有 YAML 文件无需增加任何新字段。
- configurable 类注册 API 的现有调用方式保持有效。
- `get_object()` 仍然每次返回新实例。
- `GPConfig.config` 的保存内容不得出现 manager、context 或规范路径。
- `GPConfig.save()` 的输出不得因本重构产生额外字段。

## 验收标准

自动化测试至少覆盖：

1. 旧式 `GPConfigurable(config)` 子类可通过 manager 和 folder 的 `get_object()` 正常创建。
2. 自定义 `from_config()` 收到发起调用的同一个 manager 实例。
3. manager 入口传入的等价路径生成同一个规范 context 路径。
4. folder 入口生成包含 folder 前缀的完整规范路径。
5. 自定义钩子能够通过 `context.manager` 加载同一配置树中的另一个配置。
6. 钩子抛出的异常原样传播，且默认构造器不会被重试调用。
7. 钩子返回错误类型时立即触发构造契约异常。
8. 配置保存结果不包含 manager、context 或 context 路径。
9. 两个不同 manager 构造的对象各自收到正确的 manager，不共享隐式全局状态。
10. 现有 gpconfig 测试套件全部通过。

## Quant Types 当前决策

在该 gpconfig 能力发布并被 Quant Types 依赖之前，Portfolio v1 不继承
`GPConfigurable`，也不声明支持 `GPConfigManager.get_object()`。v1 的唯一完整解析入口为：

```python
PortfolioResolver(manager).resolve("portfolio.all_weather")
```

未来接入上下文构造钩子时，应复用 resolver，不复制任何 portfolio 递归或权重逻辑。
