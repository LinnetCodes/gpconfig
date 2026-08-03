# gpconfig 上下文感知对象构造设计

## 状态

- 日期：2026-08-02
- 状态：已批准，待用户复核
- 目标分支：`context-aware-object-construction-refactor`
- 基于版本：gpconfig 0.3.4
- 输入需求：[原始需求](../gpconfig-context-aware-object-construction-refactor.md)

## 需求合理性结论

该需求合理，且应由 gpconfig 提供通用能力。

当前 `GPConfigManager.get_object(path)` 只把一个配置对象传给已注册类的单参数构造器。需要在构造期间解析同一配置树内其他配置的对象无法取得发起调用的 manager、统一的配置根目录和该 manager 的缓存，只能依赖全局状态、反向推断路径、动态污染配置对象或延迟初始化。这些替代方案都会削弱依赖显式性、缓存一致性或对象有效性。

把构造上下文放在 gpconfig 的对象构造边界，同时把领域递归、循环检测和聚合逻辑留给下游库，符合 `GPConfig`、`GPConfigurable` 和 `GPConfigManager` 的现有职责划分。

## 目标

1. 让 configurable 对象在构造期间取得发起调用的 manager 和当前 YAML 文件的规范点路径。
2. 保持 `GPConfig` 为纯配置数据，不向其中注入 manager、context 或额外 I/O 能力。
3. 保持标准旧式 `GPConfigurable(config)` 子类无需修改即可继续构造。
4. 让 manager 和 folder 入口产生相同的构造语义。
5. 保持 `get_object()` 每次创建新对象，不增加对象缓存。
6. 对构造钩子的异常和错误返回值执行 fail-fast，不回退或重试。
7. 强化注册契约，只允许 `GPConfigurable` 子类进入 configurable 注册表。

## 非目标

- 不改变 YAML 中 `cfg_class_name` 或 `configured_class_name` 的含义或格式。
- 不改变 `GPConfigManager.get_config()` 的缓存、文件/文件夹优先级或加载策略。
- 不把构造上下文保存到 `GPConfig` 或自动保存到构造出的对象。
- 不实现下游领域的引用递归、循环检测、最大深度或聚合规则。
- 不增加刷新、监听、惰性重载或对象缓存。
- 不在本次工作中更新现有 README、MkDocs 英文/中文页面、导航、版本号或发布说明。

## 方案比较与决策

### 采用：不可变上下文和类级构造钩子

新增公开的 `GPConfigurableContext`，并在 `GPConfigurable` 上增加 `from_config()` 类方法。manager 始终通过该钩子构造已注册对象，默认钩子继续调用 `cls(config)`。

该方案把上下文限制在构造边界，能够保持配置数据纯净，并提供单一、可覆盖、可验证的扩展点。

### 未采用：向 `__init__` 注入 context

该方案需要反射构造器签名，或在捕获 `TypeError` 后重试旧式构造器。前者容易对装饰器、继承和可变参数产生误判，后者可能掩盖构造器内部真正的错误，并违反 fail-fast 要求。

### 未采用：单独注册对象工厂

额外的工厂注册会形成类注册和工厂注册两套关联机制，需要新增优先级、冲突与生命周期规则。对于当前单一构造扩展点需求，这会产生不必要的 API 和状态复杂度。

## 公开 API

### `GPConfigurableContext`

在 `gpconfig.configurable` 中新增：

```python
@dataclass(frozen=True, slots=True)
class GPConfigurableContext:
    manager: "GPConfigManager"
    path: str
```

字段语义：

- `manager` 是接收 `get_object()` 调用的原始 `GPConfigManager` 实例。
- `path` 是实际 YAML 文件相对于 `manager.cfg_folder` 的规范点路径，不含项目名前缀和 `.yaml` 后缀。
- frozen 约束只阻止替换 context 字段，不代表 manager 自身不可变。

该类型从 `gpconfig` 顶层导出。

### `GPConfigurable.from_config()`

在 `GPConfigurable` 上新增默认类方法：

```python
@classmethod
def from_config(
    cls: type[GPConfigurableT],
    config: "GPConfig",
    *,
    context: GPConfigurableContext,
) -> GPConfigurableT:
    return cls(config)
```

- `context` 必须以关键字传入。
- 默认实现不读取、修改或保存 context，只调用旧式单参数构造器。
- 返回类型使用绑定到 `GPConfigurable` 的 `TypeVar`，不使用 Python 3.11 才引入的 `Self`。
- 覆盖实现可以使用 manager 解析其他配置，也可以在返回对象前丢弃 context。

### `ConfigurableConstructionError`

在 `gpconfig.exceptions` 中新增直接继承 `GPConfigError` 的公开异常：

```python
class ConfigurableConstructionError(GPConfigError):
    def __init__(
        self,
        path: str,
        expected_type: type,
        actual_type: type,
    ) -> None:
        ...
```

异常公开保存：

- `path`：规范配置路径；
- `expected_type`：注册的 configurable 类；
- `actual_type`：钩子实际返回值的类型。

该异常只表示钩子正常返回后违反返回类型契约，不用于包装钩子自身抛出的异常。它从 `gpconfig` 顶层导出。

## 注册契约

`GPConfigManager.register_configurable_class()` 在读取类名或修改注册表之前验证参数：

1. 参数必须是类；
2. 参数必须是 `GPConfigurable` 的子类。

任一条件不满足时抛出 `RegistrationError`，并保持注册表不变。不使用 `inspect.signature()` 校验 `from_config()` 覆盖实现。

对合法类型保留现有行为：

- 重复注册同一个类仍然幂等；
- 不同类使用相同 `__name__` 时仍然抛出 `RegistrationError`。

公开类型标注收紧为 `type[GPConfigurable]`，运行时检查负责保护从未经过静态类型检查的调用。

## 规范路径

manager 使用现有 `_parse_path(path)` 得到实际 YAML 文件，随后：

1. 计算该文件相对于 `cfg_folder` 的路径；
2. 移除 `.yaml` 后缀；
3. 用 `.` 连接各路径段。

因此：

```python
manager.get_object("services.api")
manager.get_object("myproject.services.api")
```

都会生成：

```python
context.manager is manager
context.path == "services.api"
```

`GPConfigFolder.get_object("api")` 继续先组合 folder 的规范相对路径，再委托原 manager。例如 `services` folder 会传入 `services.api`，得到相同的 context。folder 不创建第二种上下文，也不替换 manager。

本次不新增对尾随 YAML 键路径的验证或其他路径规则。若传入路径包含现有解析规则识别出的 YAML 内部键，context 的 `path` 仍表示底层 YAML 文件，而不是键路径。

## 对象构造数据流

`GPConfigManager.get_object(path)` 按以下顺序执行：

1. 调用 `get_config(path, _force_file=True)`，保留现有文件优先和配置缓存语义；
2. 从配置取得 `configured_class_name`；
3. 从 `_configurable_classes` 查找已注册类，保留现有缺失和未注册异常；
4. 解析实际 YAML 文件并生成规范路径；
5. 创建 `GPConfigurableContext(manager=self, path=canonical_path)`；
6. 调用且只调用一次 `configurable_cls.from_config(config, context=context)`；
7. 用 `isinstance(result, configurable_cls)` 验证结果，允许返回注册类的子类实例；
8. 返回结果，不写入对象缓存。

自定义钩子通过 `context.manager.get_config()` 或 `context.manager.get_object()` 发起的后续读取，会复用同一 manager 的配置根目录和实例级配置缓存。

## 错误处理

- 现有配置路径、配置验证、缺少 `configured_class_name` 和未注册类异常保持不变。
- `from_config()` 抛出的业务异常原样传播，不包装。
- 覆盖方法签名错误产生的 `TypeError` 原样传播。
- 钩子抛出任何异常后都不得调用 `configurable_cls(config)` 重试。
- 钩子返回值不是注册类实例时，立即抛出 `ConfigurableConstructionError`。
- 错误返回值不缓存，也不以其他方式返回给调用者。

## Breaking change 与适配指导

本次改动是有意的 breaking change：

1. 当前实现偶然允许注册的非 `GPConfigurable` 类型将改为在注册阶段失败；
2. 现有 `GPConfigurable` 子类若已经定义其他语义或不兼容签名的 `from_config()`，manager 将调用该方法并立即暴露冲突。

实现阶段新增独立文档：

```text
dev_docs/gpconfig-context-aware-object-construction-migration-guide.md
```

该文档说明：

- 标准单参数 `GPConfigurable(config)` 子类无需修改；
- 非子类类型如何改为继承 `GPConfigurable`；
- 既有同名工厂方法如何重命名，或如何适配 `config, *, context` 签名；
- 自定义钩子的返回类型和异常传播契约；
- YAML、注册名称和配置保存格式不需要迁移。

除该新增适配指导以及 superpowers 流程产生的新设计和实施计划外，不修改任何现有文档。

## 测试设计

自动化测试覆盖：

1. 默认 `from_config()` 继续调用单参数构造器并返回正确子类。
2. context 使用 frozen、slots，字段不能重新赋值。
3. manager 入口把原始 manager 实例传给钩子。
4. 带和不带项目名前缀的等价路径产生相同规范路径。
5. folder 入口产生带 folder 前缀的完整规范路径和相同 manager。
6. 钩子能够通过 context 读取同一配置树中的另一配置，并复用当前 manager 缓存。
7. 每次 `get_object()` 调用一次钩子并返回新对象。
8. 两个 manager 分别提供自己的 context，不共享隐式全局状态。
9. 钩子异常保持原对象身份传播，且不重试默认构造器。
10. 错误返回类型触发 `ConfigurableConstructionError`，并暴露正确的结构化属性。
11. 非类和非 `GPConfigurable` 类注册失败，且注册表不变。
12. 合法类型重复注册和同名冲突继续遵守现有规则。
13. context、manager 和规范路径不进入 `GPConfig` 或保存后的 YAML。
14. 新 context 和异常可从 `gpconfig` 顶层导入。
15. 现有测试套件全部通过。

测试沿用现有 pytest 组织方式，并在涉及类级注册表的测试前后调用 `GPConfigManager.reset_registries()`。

最终验证命令：

```powershell
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m pytest --cov=gpconfig
.venv/Scripts/python.exe -m ruff check .
```

## 预期修改范围

实现阶段预计只修改：

```text
src/gpconfig/configurable.py
src/gpconfig/manager.py
src/gpconfig/exceptions.py
src/gpconfig/__init__.py
tests/test_configurable.py
tests/test_manager_objects.py
tests/test_gpconfig_folder.py
tests/test_exceptions.py
tests/test_exports.py
dev_docs/gpconfig-context-aware-object-construction-migration-guide.md
```

测试场景应优先加入已有相关测试文件；没有必要时不新增测试模块。现有文档、版本号、发布自动化和下游领域代码均不在修改范围内。
