# Reject Duplicate YAML Keys 工作流进度

**最后更新：** 2026-08-02
**当前分支：** `reject-duplicate-yaml-keys`
**当前阶段：** Implementation plan 已完成并提交，正在等待用户审核；尚未开始实现

## 恢复会话时先做什么

1. 阅读仓库根目录的 `AGENTS.md`，尤其是 `.venv`、测试、文档同步和版本规则。
2. 确认当前分支与工作区：

   ```powershell
   git branch --show-current
   git status --short --branch
   ```

3. 阅读已批准的设计：
   `docs/superpowers/specs/2026-08-02-reject-duplicate-yaml-keys-design.md`。
4. 阅读待审核的实现计划：
   `docs/superpowers/plans/2026-08-02-reject-duplicate-yaml-keys.md`。
5. 当前门控是用户审核 implementation plan。除非用户明确批准该计划，否则不要修改
   `src/`、`tests/`、产品文档、changelog 或版本号。
6. 用户批准后，按照 implementation plan 顶部要求调用
   `superpowers:subagent-driven-development`（推荐）或
   `superpowers:executing-plans`，逐任务执行并保留 TDD/验证检查点。

## 原始任务

阅读 `dev_docs/gpconfig-reject-duplicate-yaml-keys.md`，验证 gpconfig 是否会静默接受
YAML 重复键；若问题存在，则设计和规划修复。实现完成时版本升级到 `0.3.5`，必要时同步
中英文文档并更新 changelog。整个工作遵循 Superpowers 流程，并在 implementation plan
完成后停下等待用户审核。所有必要提交均在 `reject-duplicate-yaml-keys` 分支完成。

## 已验证结论

- 问题真实存在。
- 修复前完整基线为 **262 passed**：

  ```powershell
  .venv\Scripts\python.exe -m pytest
  ```

- 当前环境使用 PyYAML `6.0.3`。`yaml.safe_load()` 会在同一个 mapping 中静默保留最后
  一个重复键的值。
- 已实际复现以下全部场景：
  - 顶层 mapping 重复键；
  - 嵌套 mapping 重复键；
  - list 元素中的 mapping 重复键；
  - 普通配置文件；
  - `global_env.yaml`。
- 根因是 PyYAML 的 mapping constructor 最终直接执行 `mapping[key] = value`，没有重复
  检查；重复信息在 Pydantic 收到普通 `dict` 之前已经丢失。
- PyYAML 官方 issue [#165](https://github.com/yaml/pyyaml/issues/165) 于
  2018-05-10 提交，当前仍为 Open，无负责人、milestone 或关联实现 PR。最新版和官方
  `main` 分支均未提供重复键拒绝选项。

## 用户已确认的需求与决策

- 使用推荐方案：新增私有安全 YAML Loader 模块，而不是更换 YAML 包或解析两次。
- 私有模块仍使用 PyYAML；Loader 必须继承 `yaml.SafeLoader`。
- 文本不同但经 SafeLoader 解析后成为相等 Python 键的写法也必须拒绝，例如：
  - `1` 与 `true`；
  - `null` 与 `~`。
- 检查只针对同一个 mapping 中的重复显式键。
- 不同 mapping 中的同名键合法。
- YAML merge key `<<` 不属于本次重复显式键检查；合法 merge 和显式覆盖行为必须保持。
- 不增加兼容开关，不保留“最后一个值获胜”的路径。
- 公共异常继续使用 `ConfigValidationError`，底层 YAML 异常同时保存在
  `.original_error` 和 `.__cause__`。
- 错误诊断必须包含文件路径、可读键名、首次定义的行列号和重复定义的行列号。
- 版本只在 `src/gpconfig/__init__.py` 中从 `0.3.4` 升级为 `0.3.5`。
- 英文和中文文档必须同步。

## 已批准设计的关键点

新增 `src/gpconfig/_yaml.py`：

- `_RejectDuplicateKeysSafeLoader(yaml.SafeLoader)` 覆写
  `construct_mapping()`。
- 在 merge 展开前保存当前 mapping 的显式 key nodes，但在 SafeLoader 完成 tag/merge
  处理后构造并比较键。
- 发现重复时抛出 `yaml.constructor.ConstructorError`，context mark 指向首次定义，
  problem mark 指向重复定义。
- 无重复时委托 PyYAML 原有 `SafeLoader` mapping 构造逻辑。
- 提供 `load_yaml(stream: TextIO) -> Any`，内部调用
  `yaml.load(stream, Loader=_RejectDuplicateKeysSafeLoader)`。安全性由 SafeLoader 子类保证，
  不启用任意 Python 对象构造。
- `GPConfigManager._load_yaml_dict()` 只把 `yaml.safe_load(f)` 替换为 `load_yaml(f)`；现有
  文件打开、异常包装、空文件归一化和顶层 mapping 校验不变。

### 重要兼容性陷阱

不要用直接返回 `dict` 的函数替换 PyYAML 默认 mapping tag constructor。PyYAML 的
`construct_yaml_map()` 是生成器，负责支持递归 anchor/alias mapping；绕过它会导致合法
自引用 YAML 报 `unconstructable recursive node`。正确方案是覆写 SafeLoader 的
`construct_mapping()`，保留继承的生成器 constructor。

也不要调用 `yaml.SafeLoader.add_constructor(...)` 修改全局注册表。私有 Loader 不得改变
应用代码直接调用 `yaml.safe_load()` 时的原有行为。

已用临时脚本验证计划中的 Loader 代码能够同时满足：

- 拒绝普通、解析后相等和深层重复键；
- 保留 merge key 显式覆盖；
- 保留递归 alias 对象 identity；
- 不污染全局 `yaml.SafeLoader`。

## 当前 Git 状态与提交

创建本文件前工作区干净。规划阶段已经产生以下提交：

```text
9e9e9c3 docs: add duplicate YAML key implementation plan
d2f81a9 docs: preserve recursive YAML mapping behavior
67062e8 docs: add duplicate YAML key rejection design
```

分支基点是 `8410bb8`（`version-0.3.4`）。未创建额外 worktree；用户明确要求在当前干净
分支直接工作。

## 当前未完成的工作

以下内容均尚未实现：

- `src/gpconfig/_yaml.py` 尚不存在。
- `src/gpconfig/manager.py` 仍调用 `yaml.safe_load()`。
- 重复键回归测试尚未加入 `tests/test_yaml_loading.py`。
- `docs/exceptions.md`、`docs/zh/exceptions.md`、`docs/manager.md`、
  `docs/zh/manager.md` 尚未更新重复键契约。
- `CHANGELOG.md` 尚无 `0.3.5` 条目。
- `src/gpconfig/__init__.py` 仍为 `__version__ = "0.3.4"`。

## Implementation plan 摘要

完整、可执行的计划位于
`docs/superpowers/plans/2026-08-02-reject-duplicate-yaml-keys.md`，共三个任务：

1. 先写失败测试，再实现私有 SafeLoader 和 manager 集成；提交：
   `fix: reject duplicate YAML mapping keys`。
2. 同步英文/中文异常与 manager 文档，增加 0.3.5 changelog；提交：
   `docs: document duplicate YAML key validation`。
3. 将版本升级到 `0.3.5`，执行完整发布验证；提交：
   `chore: bump version to 0.3.5`。

计划包含完整测试代码、实现代码、文档文本、预期结果和逐步命令。执行时不要凭本进度摘要
自行重写方案，应以 implementation plan 为准。

## 必须使用的验证命令

所有 Python 命令必须使用仓库 `.venv`：

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mkdocs build --strict
git diff --check
```

完成实现前还需确认：

- `gpconfig.__version__ == "0.3.5"`；
- 工作区干净；
- 只有计划批准的 loader、manager、测试、中英文文档、changelog 和版本文件发生变化；
- `pyproject.toml`、README、缓存和保存逻辑没有变化。
