# Context-Aware Object Construction Workflow Progress

## 当前状态

- 日期：2026-08-02
- 分支：`context-aware-object-construction-refactor`
- 工作流阶段：implementation plan 已完成并提交，正在等待用户审阅
- 实现状态：尚未修改任何源代码、测试或迁移指南
- 下一门禁：用户明确批准 implementation plan 并指示开始实现之前，不得进入实现

## 下次会话的建议阅读顺序

1. 仓库根目录的 `AGENTS.md`，特别是 `.venv`、测试、文档和 Git 约束。
2. 本文件，恢复当前工作流状态。
3. [原始需求](../../dev_docs/gpconfig-context-aware-object-construction-refactor.md)。
4. [已批准设计](specs/2026-08-02-context-aware-object-construction-design.md)。
5. [待审阅 Implementation Plan](plans/2026-08-02-context-aware-object-construction.md)。

## 已完成的 Superpowers 工作流

1. 已读取并遵循 `superpowers:using-superpowers` 及 Codex 平台适配说明。
2. 已使用 `superpowers:brainstorming`：
   - 阅读需求、相关源码、测试、现有文档和近期提交；
   - 验证需求合理性和兼容性风险；
   - 比较三种方案；
   - 分四部分取得用户设计批准；
   - 写入、自检并提交设计文档；
   - 取得用户对书面设计的批准。
3. 已使用 `superpowers:writing-plans`：
   - 生成包含 5 个任务、35 个测试先行步骤的 implementation plan；
   - 完成需求覆盖、占位符和跨任务类型一致性自检；
   - 提交 implementation plan。
4. 当前按用户要求停在 implementation plan 审阅门禁，没有开始实现。

## 需求合理性结论

需求合理，应由 gpconfig 提供通用的对象构造上下文。当前
`GPConfigManager.get_object(path)` 只执行 `configurable_cls(config)`，无法向需要解析同一
配置树中其他配置的对象显式提供原始 manager、规范配置路径和同一 manager 的缓存语义。

选定的边界保持 `GPConfig` 为纯配置数据，只在 configurable 对象的构造入口传递上下文；
portfolio 等领域递归、循环检测、深度限制和聚合逻辑继续由下游库负责。

## 已批准的关键决策

### 采用方案 A

新增不可变公开上下文：

```python
@dataclass(frozen=True, slots=True)
class GPConfigurableContext:
    manager: GPConfigManager
    path: str
```

给 `GPConfigurable` 新增类级钩子：

```python
@classmethod
def from_config(
    cls,
    config: GPConfig,
    *,
    context: GPConfigurableContext,
) -> GPConfigurable:
    return cls(config)
```

实际实现使用绑定 `TypeVar`，保持 Python 3.10 支持，不使用 `Self`。

### 注册契约

- `GPConfigManager.register_configurable_class()` 只接受 `GPConfigurable` 子类。
- 注册时同时拒绝非类参数和非子类类型，抛出 `RegistrationError`，且不修改注册表。
- 只校验继承关系，不使用 `inspect.signature()` 检查 `from_config()` 签名。
- 同一个类重复注册仍然幂等；不同同名类仍然冲突。

### 构造和路径契约

- manager 从实际 YAML 文件生成相对于 `cfg_folder` 的规范点路径，不含 `.yaml` 和可选的项目名前缀。
- `services.api` 与 `project_name.services.api` 得到相同的 `context.path == "services.api"`。
- `GPConfigFolder.get_object()` 继续组合 folder 前缀并委托原 manager，不创建另一套上下文。
- manager 只调用一次 `configurable_cls.from_config(config, context=context)`。
- 钩子异常和错误签名产生的 `TypeError` 原样传播，不包装、不回退、不重试旧构造器。
- 钩子返回值必须满足 `isinstance(result, configurable_cls)`，因此允许返回注册类的子类实例。
- 错误返回类型触发新的公开异常 `ConfigurableConstructionError`。
- `get_object()` 仍然每次返回新对象，不增加对象缓存。

### Breaking change 结论

本次是有意的 breaking change，不兼容：

1. 当前实现偶然允许注册的非 `GPConfigurable` duck-typed 类型；
2. 已有但不符合新签名或具有其他语义的同名 `from_config()` 方法。

因此 implementation plan 要求新增：

```text
dev_docs/gpconfig-context-aware-object-construction-migration-guide.md
```

该迁移指南尚未创建，将在实现阶段创建。

## 范围约束

- 不改变 YAML schema、`cfg_class_name` 或 `configured_class_name`。
- 不向 `GPConfig` 添加 manager、context 或规范路径字段。
- 不改变 `GPConfig.save()` 输出。
- 不改变配置缓存、配置目录解析、文件/文件夹优先级或对象非缓存语义。
- 不修改现有 `README.md`、`docs/`、`docs/zh/`、`mkdocs.yml` 或发布工作流。
- superpowers 新增的设计、计划、本进度文件，以及 breaking-change 迁移指南不属于现有文档修改。
- 不调整 `src/gpconfig/__init__.py` 中的 `__version__ = "0.3.4"`；版本和正式发布说明留给后续集中发布工作。
- 所有 Python 命令必须使用 `.venv/Scripts/python.exe`。

## 已完成的基线验证

在设计阶段、任何实现修改之前执行：

```text
.venv/Scripts/python.exe -m pytest
262 passed in 1.33s

.venv/Scripts/python.exe -m ruff check .
All checks passed!
```

运行环境显示 Python 3.13.12。实现完成前必须按 implementation plan 重新运行聚焦测试、全量
pytest、coverage 和 Ruff；不得把这里的历史基线当成实现完成证据。

## 当前提交

- `d66540d docs: design context-aware object construction`
- `14c4505 docs: plan context-aware object construction`

创建本文件之前，分支工作区已确认干净。

## 下一步

1. 等待用户审阅
   [implementation plan](plans/2026-08-02-context-aware-object-construction.md)。
2. 若用户要求修改计划，只修改计划及本进度记录，重新自检并提交；仍不进入实现。
3. 若用户批准计划并明确要求开始实现，按照计划头部要求选择相应的 Superpowers 执行技能，
   严格逐任务执行测试失败、最小实现、测试通过和提交循环。
4. 实现阶段不得跳过迁移指南，不得更新现有文档或版本号。
5. 工作流状态变化后更新本文件，使它继续成为下一会话的恢复入口。
