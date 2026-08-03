# Context-Aware Construction User Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bilingual (EN + ZH) user documentation for the context-aware object construction feature, so users learn when to override `GPConfigurable.from_config()`, how to write one, what `GPConfigurableContext` carries, and the cycle/cache pitfalls — without changing code, tests, version, or mkdocs nav.

**Architecture:** Extend the two existing API doc pages (`configurable.md`, `manager.md`) in both `docs/` and `docs/zh/`, mirroring content per the i18n folder convention. Add a full "Context-Aware Construction" section to `configurable.md` and a short cross-linking paragraph to `manager.md`'s `get_object` section. Verify the runnable doc example actually executes under the `.venv` interpreter before committing.

**Tech Stack:** Markdown (mkdocs Material + i18n plugin), Python 3.10+ via `.venv/Scripts/python.exe`, gpconfig public API.

## Global Constraints

- Run every Python command with `.venv/Scripts/python.exe`; never bare `python`/`pip`/`pytest`/`ruff`.
- Modify ONLY these four files: `docs/configurable.md`, `docs/zh/configurable.md`, `docs/manager.md`, `docs/zh/manager.md`. No new page, no `mkdocs.yml` change.
- Do NOT touch `src/gpconfig/**`, `tests/**`, `src/gpconfig/__init__.py` `__version__` (stays `0.3.4`), README, `.github/**`, or `dev_docs/**`.
- The canonical class spelling is `GPConfigurable`, the context is `GPConfigurableContext`, the exception is `ConfigurableConstructionError`.
- Bilingual parity: every EN section/heading/code block/table/constraint bullet has a ZH counterpart with identical code and equivalent prose. Headings mirror the existing page's language style (EN: "Context-Aware Construction"; ZH: "上下文感知构造").
- The runnable example must use only the stable public API already shipped on this branch: `GPConfig`, `GPConfigurable`, `GPConfigurableContext`, `GPConfigManager`, `register_config_class`, `register_configurable_class`, `get_config`, `get_object`. No invented methods or attributes.
- The example verification script is throwaway — it is NOT committed. Only the four doc files are committed.
- Work and commit only on `context-aware-object-construction-refactor`.

---

## File Structure

### Files modified

- `docs/configurable.md` — new `## Context-Aware Construction` section between `## config Property` (ends ~line 112) and `## Complete Example` (line 114).
- `docs/zh/configurable.md` — ZH mirror `## 上下文感知构造` between `## config 属性` (ends ~line 112) and `## 完整示例` (line 114).
- `docs/manager.md` — short `from_config` dispatch paragraph + cross-link appended to the `### get_object()` section (after its `**Note:**` bullets at line 384, before `### list_configs()` at line 386).
- `docs/zh/manager.md` — ZH mirror appended to the `### get_object()` section (after its `**注意：**` bullets at line 381, before `### list_configs()` at line 383).

No new files. No deletions.

---

### Task 1: Verify and Lock the Runnable Example

**Files:**
- Create (throwaway, NOT committed): a temporary script under the OS temp dir or repo-root-ignored scratch to exercise the doc example.

**Interfaces:**
- Consumes: the shipped public API on this branch (`GPConfigurableContext`, `GPConfigurable.from_config(config, *, context)`, `GPConfigManager.get_config`, `GPConfigManager.get_object`, `register_config_class`, `register_configurable_class`).
- Produces: a verified, copy-pasteable example block (config classes, configurable class, YAML, registration, usage) that Task 2 embeds verbatim in both doc pages.

This task comes FIRST so that the example is proven before it is written into docs. Doc code that does not run is the primary failure mode for this kind of work; locking it up front prevents a re-write loop in Task 2.

- [ ] **Step 1: Confirm branch and clean tree**

Run:

```bash
git branch --show-current
git status --short
```

Expected: branch is `context-aware-object-construction-refactor`; no uncommitted files.

- [ ] **Step 2: Write the example as a runnable script**

Create a throwaway file (e.g. `D:/Projects/gp_infra/gpconfig/.verify_example.py` — note: NOT under `tests/`, NOT to be committed). Use this exact content:

```python
"""Throwaway verification of the context-aware-construction doc example.

Proves the example that will be embedded in docs/configurable.md actually runs
and produces the values the docs claim. NOT committed.
"""
from typing import ClassVar

from gpconfig import GPConfig, GPConfigurable, GPConfigManager
from gpconfig.configurable import GPConfigurableContext


class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432


class WorkerConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "WorkerConfig"
    worker_name: str
    concurrency: int = 4


class Worker(GPConfigurable):
    """A worker that needs the database config to do its job."""

    def __init__(self, config: WorkerConfig) -> None:
        super().__init__(config)
        self.worker_name = config.worker_name
        self.concurrency = config.concurrency
        self.database = None  # filled in by from_config

    @classmethod
    def from_config(
        cls,
        config: WorkerConfig,
        *,
        context: GPConfigurableContext,
    ) -> "Worker":
        # context.manager is the manager that received the get_object() call.
        # Use it to read a related config from the SAME config tree.
        # get_config returns config DATA (cached per file) — it does NOT
        # construct an object and does NOT recurse.
        db_config = context.manager.get_config("database", DatabaseConfig)

        obj = cls(config)
        obj.database = db_config
        return obj


def main(tmp_dir: str) -> None:
    import os

    os.makedirs(tmp_dir, exist_ok=True)
    with open(os.path.join(tmp_dir, "global_env.yaml"), "w", encoding="utf-8") as f:
        f.write("version: 1.0\n")
    with open(os.path.join(tmp_dir, "database.yaml"), "w", encoding="utf-8") as f:
        f.write(
            'cfg_class_name: "DatabaseConfig"\n'
            "host: db.internal\n"
            "port: 5432\n"
        )
    with open(os.path.join(tmp_dir, "worker.yaml"), "w", encoding="utf-8") as f:
        f.write(
            'cfg_class_name: "WorkerConfig"\n'
            'configured_class_name: "Worker"\n'
            "worker_name: ingest\n"
            "concurrency: 8\n"
        )

    GPConfigManager.reset_registries()
    GPConfigManager.register_config_class(DatabaseConfig)
    GPConfigManager.register_config_class(WorkerConfig)
    GPConfigManager.register_configurable_class(Worker)

    manager = GPConfigManager("myapp", cfg_folder=tmp_dir)
    worker = manager.get_object("worker")

    # Assertions that the docs will claim:
    assert isinstance(worker, Worker)
    assert worker.worker_name == "ingest"
    assert worker.concurrency == 8
    assert worker.database.host == "db.internal"
    assert worker.database.port == 5432

    # Object non-caching: two get_object calls return distinct instances.
    w2 = manager.get_object("worker")
    assert w2 is not worker

    print("EXAMPLE OK")


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        main(d)
```

- [ ] **Step 3: Run the script and confirm it prints `EXAMPLE OK`**

Run:

```bash
.venv/Scripts/python.exe .verify_example.py
```

Expected: prints `EXAMPLE OK` and exits 0. If it fails, fix the script (not the library) until it passes — the library API is fixed and reviewed; the example must conform to it.

- [ ] **Step 4: Clean up the throwaway script**

Run:

```bash
rm .verify_example.py
git status --short
```

Expected: working tree clean (the script was never tracked). Confirm `git status` shows nothing.

Do NOT commit anything in this task. The deliverable is the verified example text, which Task 2 embeds.

---

### Task 2: Add the "Context-Aware Construction" Section to Both Doc Pages

**Files:**
- Modify: `docs/configurable.md` (insert section between `## config Property` block and `## Complete Example`).
- Modify: `docs/zh/configurable.md` (insert ZH mirror section between `## config 属性` block and `## 完整示例`).

**Interfaces:**
- Consumes: the verified example from Task 1 (use the class/YAML/assertion content verbatim).
- Produces: the full user-facing guidance section in both languages.

- [ ] **Step 1: Insert the EN section into `docs/configurable.md`**

Insert the following block immediately BEFORE the `## Complete Example` line (currently line 114), i.e. right after the `## config Property` section ends (after the `print(cache.config.ttl)  # Access field from config` code block's closing fence at ~line 112). Use this exact content:

````markdown
## Context-Aware Construction

### When to Override `from_config()`

Most subclasses do **not** need to override anything. The default
`GPConfigurable.from_config(config, *, context)` simply calls `cls(config)`, so a
standard single-argument subclass keeps working unchanged:

```python
class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)   # nothing else required
```

Override `from_config()` **only when** the object must reference other configs in
the same config tree at construction time. The `context` argument is the only way
for the object to reach the manager that built it — `GPConfig` carries no manager
field by design.

### The Construction Hook and Context

```python
from gpconfig import GPConfigurable, GPConfigurableContext


class Worker(GPConfigurable):
    @classmethod
    def from_config(
        cls,
        config: WorkerConfig,
        *,
        context: GPConfigurableContext,
    ) -> "Worker":
        # context.manager: the GPConfigManager that received this get_object() call.
        # context.path:    canonical dotted path of this object's YAML file,
        #                  with the .yaml suffix and any project-name prefix stripped
        #                  (e.g. "services.api" and "myapp.services.api" both give
        #                  context.path == "services.api").
        return cls(config)
```

`GPConfigurableContext` is a frozen, slotted value object with exactly two fields:

| Field     | Meaning                                                                                  |
|-----------|------------------------------------------------------------------------------------------|
| `manager` | The `GPConfigManager` that received this `get_object()` request.                         |
| `path`    | Canonical dotted path of the source YAML file (no `.yaml`, no project-name prefix).      |

### Example: Referencing Another Config

A `Worker` that needs the database config. It reads it through
`context.manager.get_config(...)`, which returns the config **data** without
constructing a `Database` object:

```python
from typing import ClassVar

from gpconfig import GPConfig, GPConfigurable, GPConfigManager
from gpconfig.configurable import GPConfigurableContext


class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432


class WorkerConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "WorkerConfig"
    worker_name: str
    concurrency: int = 4


class Worker(GPConfigurable):
    def __init__(self, config: WorkerConfig) -> None:
        super().__init__(config)
        self.worker_name = config.worker_name
        self.concurrency = config.concurrency
        self.database = None

    @classmethod
    def from_config(
        cls,
        config: WorkerConfig,
        *,
        context: GPConfigurableContext,
    ) -> "Worker":
        db_config = context.manager.get_config("database", DatabaseConfig)
        obj = cls(config)
        obj.database = db_config
        return obj
```

**YAML files:**

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
host: db.internal
port: 5432
```

```yaml
# worker.yaml
cfg_class_name: "WorkerConfig"
configured_class_name: "Worker"
worker_name: ingest
concurrency: 8
```

```python
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_config_class(WorkerConfig)
GPConfigManager.register_configurable_class(Worker)

manager = GPConfigManager("myapp")
worker = manager.get_object("worker")
print(worker.worker_name)        # ingest
print(worker.database.host)     # db.internal
```

### Choosing Between `get_config` and `get_object` Inside a Hook

The two manager calls a hook can make behave very differently:

| Call                                     | Calls `from_config`? | Recurses? | Cached?                  |
|------------------------------------------|:--------------------:|:---------:|--------------------------|
| `context.manager.get_config(path, Cfg)`  | No                   | No        | Yes — config data, per file |
| `context.manager.get_object(path)`       | Yes                  | Yes       | No — a new object each call |

Use `get_config` to read another config's **data**. Use `get_object` only when you
need another fully-constructed **object** (and accept that it recurses through
*its* `from_config`).

### Important Constraints

- The hook **must** return an instance of the registered configurable class (a
  subclass instance is also allowed). Any other return value raises
  `ConfigurableConstructionError`.
- Exceptions raised by the hook — including `TypeError` from an incompatible
  signature — propagate unchanged. The manager never retries the legacy
  `cls(config)` constructor after a hook fails.
- `get_object()` does **not** cache objects; every call returns a fresh instance.
  `get_config()` **does** cache config data per file.
- **Cycle detection is the caller's responsibility.** The manager performs no
  cycle detection or depth limiting. If `get_object("a")`'s hook calls
  `get_object("b")` whose hook calls back `get_object("a")`, it recurses without
  bound and overflows the stack.

> The default `from_config()` preserves the standard-subclass contract, so most
> users never need to override it.
````

- [ ] **Step 2: Insert the ZH mirror section into `docs/zh/configurable.md`**

Insert immediately BEFORE the `## 完整示例` line (line 114), right after the `## config 属性` section ends. Use this exact content (code blocks identical to EN; prose in Simplified Chinese):

````markdown
## 上下文感知构造

### 何时重写 `from_config()`

大多数子类**不需要**重写任何东西。默认的
`GPConfigurable.from_config(config, *, context)` 只是调用 `cls(config)`，所以标准的
单参数子类无需任何改动即可继续工作：

```python
class Database(GPConfigurable):
    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)   # 无需其它代码
```

**仅当**对象在构造时需要引用同一配置树中的其它配置时，才需要重写 `from_config()`。
`context` 参数是对象访问构造它的 manager 的唯一途径——按设计 `GPConfig` 不携带 manager 字段。

### 构造钩子与上下文

```python
from gpconfig import GPConfigurable, GPConfigurableContext


class Worker(GPConfigurable):
    @classmethod
    def from_config(
        cls,
        config: WorkerConfig,
        *,
        context: GPConfigurableContext,
    ) -> "Worker":
        # context.manager：接收本次 get_object() 调用的 GPConfigManager。
        # context.path：   本对象 YAML 文件的规范点路径，
        #                  去掉了 .yaml 后缀和可选的项目名前缀
        #                  （例如 "services.api" 和 "myapp.services.api"
        #                  都得到 context.path == "services.api"）。
        return cls(config)
```

`GPConfigurableContext` 是一个 frozen、slotted 的值对象，只有两个字段：

| 字段      | 含义                                                                                |
|-----------|-------------------------------------------------------------------------------------|
| `manager` | 接收本次 `get_object()` 请求的 `GPConfigManager`。                                  |
| `path`    | 源 YAML 文件的规范点路径（不含 `.yaml`，不含项目名前缀）。                          |

### 示例：引用另一份配置

一个需要数据库配置的 `Worker`。它通过 `context.manager.get_config(...)` 读取数据库
配置的**数据**，而不会构造 `Database` 对象：

```python
from typing import ClassVar

from gpconfig import GPConfig, GPConfigurable, GPConfigManager
from gpconfig.configurable import GPConfigurableContext


class DatabaseConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    host: str
    port: int = 5432


class WorkerConfig(GPConfig):
    cfg_class_name: ClassVar[str] = "WorkerConfig"
    worker_name: str
    concurrency: int = 4


class Worker(GPConfigurable):
    def __init__(self, config: WorkerConfig) -> None:
        super().__init__(config)
        self.worker_name = config.worker_name
        self.concurrency = config.concurrency
        self.database = None

    @classmethod
    def from_config(
        cls,
        config: WorkerConfig,
        *,
        context: GPConfigurableContext,
    ) -> "Worker":
        db_config = context.manager.get_config("database", DatabaseConfig)
        obj = cls(config)
        obj.database = db_config
        return obj
```

**YAML 文件：**

```yaml
# database.yaml
cfg_class_name: "DatabaseConfig"
host: db.internal
port: 5432
```

```yaml
# worker.yaml
cfg_class_name: "WorkerConfig"
configured_class_name: "Worker"
worker_name: ingest
concurrency: 8
```

```python
GPConfigManager.register_config_class(DatabaseConfig)
GPConfigManager.register_config_class(WorkerConfig)
GPConfigManager.register_configurable_class(Worker)

manager = GPConfigManager("myapp")
worker = manager.get_object("worker")
print(worker.worker_name)        # ingest
print(worker.database.host)     # db.internal
```

### 在钩子中选择 `get_config` 还是 `get_object`

钩子里对 manager 的两种调用行为差别很大：

| 调用                                    | 会调用 `from_config` 吗 | 会递归吗 | 是否缓存                          |
|-----------------------------------------|:-----------------------:|:--------:|-----------------------------------|
| `context.manager.get_config(path, Cfg)` | 否                      | 否       | 是——配置数据，按文件缓存          |
| `context.manager.get_object(path)`      | 是                      | 是       | 否——每次调用都返回新对象          |

需要读取另一份配置的**数据**时用 `get_config`。只有需要另一个完整构造的**对象**时才用
`get_object`（并接受它会递归走它自己的 `from_config`）。

### 重要约束

- 钩子**必须**返回已注册可配置类的实例（也允许返回其子类的实例）。其它返回值会触发
  `ConfigurableConstructionError`。
- 钩子抛出的异常——包括签名不兼容导致的 `TypeError`——会原样传播。钩子失败后 manager
  绝不会回退重试旧式 `cls(config)` 构造器。
- `get_object()` **不**缓存对象；每次调用都返回新实例。`get_config()` **会**按文件缓存配置数据。
- **循环引用的检测由调用方负责。** manager 不做循环检测，也不限制深度。如果
  `get_object("a")` 的钩子调 `get_object("b")`，而 `get_object("b")` 的钩子又调回
  `get_object("a")`，就会无限递归直到栈溢出。

> 默认的 `from_config()` 保持了标准子类的契约，因此大多数用户无需重写它。
````

- [ ] **Step 3: Verify both pages render structurally — no broken fences**

Run a fence-balance check on the two edited files:

```bash
.venv/Scripts/python.exe -c "import sys; [print(p, open(p,encoding='utf-8').read().count('\`\`\`')) for p in ['docs/configurable.md','docs/zh/configurable.md']]"
```

Expected: each file prints an **even** number (code fences balance). If either is odd, a fence was left open — fix it.

- [ ] **Step 4: Commit the `configurable.md` changes (both languages)**

```bash
git add docs/configurable.md docs/zh/configurable.md
git commit -m "docs: document context-aware construction on GPConfigurable"
```

---

### Task 3: Cross-Link `get_object` from `manager.md` (Both Languages)

**Files:**
- Modify: `docs/manager.md` (append one paragraph + link to the `### get_object()` section, after its `**Note:**` bullets at line 384, before `### list_configs()` at line 386).
- Modify: `docs/zh/manager.md` (append ZH mirror after its `**注意：**` bullets at line 381, before `### list_configs()` at line 383).

**Interfaces:**
- Consumes: the section anchor created in Task 2 (`configurable.md` → `Context-Aware Construction`; ZH → `上下文感知构造`).
- Produces: a short dispatch explanation + cross-link, so `get_object` readers can find the override guidance.

- [ ] **Step 1: Append the EN paragraph to `docs/manager.md`'s `get_object` section**

Insert immediately AFTER the three `**Note:**` bullets that currently end the `### get_object()` section (the last bullet is `- The class corresponding to \`configured_class_name\` must be registered via \`register_configurable_class()\`` at line 384), and BEFORE the `### list_configs()` heading at line 386. Use this exact content (a blank line before and after):

````markdown

Internally, `get_object()` builds a `GPConfigurableContext(manager=self, path=<canonical>)`
— where `<canonical>` is the source YAML's dotted path with the `.yaml` suffix and any
project-name prefix stripped — and invokes
`configurable_cls.from_config(config, context=context)` **exactly once**. The return
value is validated against the registered class; a non-matching type raises
`ConfigurableConstructionError`. The default `from_config()` simply calls
`cls(config)`, so standard subclasses need no changes. To customize construction —
for example, to load related configs from the same tree — see
[Context-Aware Construction](configurable.md#context-aware-construction).

````

(The mkdocs i18n `folder` structure serves `configurable.md` at the same relative path in both locales, so the same relative link works for EN and ZH.)

- [ ] **Step 2: Append the ZH paragraph to `docs/zh/manager.md`'s `get_object` section**

Insert immediately AFTER the three `**注意：**` bullets ending the `### get_object()` section (last bullet at line 381: `- \`configured_class_name\` 对应的类必须已通过 \`register_configurable_class()\` 注册`), and BEFORE the `### list_configs()` heading at line 383. Use this exact content:

````markdown

在内部，`get_object()` 会构造一个 `GPConfigurableContext(manager=self, path=<canonical>)`
——其中 `<canonical>` 是源 YAML 的点路径，去掉了 `.yaml` 后缀和可选的项目名前缀——然后
**只调用一次** `configurable_cls.from_config(config, context=context)`。返回值会与已注册的类
校验；类型不匹配会抛出 `ConfigurableConstructionError`。默认的 `from_config()` 只是调用
`cls(config)`，所以标准子类无需任何改动。如需自定义构造——例如从同一配置树中加载关联配置
——请参阅[上下文感知构造](configurable.md#上下文感知构造)。

````

Note the ZH anchor uses the CJK heading slug. mkdocs Material with the configured
`toc.slugify_unicode` produces a slug matching the heading text, so
`#上下文感知构造` is correct.

- [ ] **Step 3: Verify both manager pages still fence-balance**

```bash
.venv/Scripts/python.exe -c "import sys; [print(p, open(p,encoding='utf-8').read().count('\`\`\`')) for p in ['docs/manager.md','docs/zh/manager.md']]"
```

Expected: both print even numbers.

- [ ] **Step 4: Commit the `manager.md` changes (both languages)**

```bash
git add docs/manager.md docs/zh/manager.md
git commit -m "docs: link get_object to context-aware construction"
```

---

### Task 4: Final Verification and Scope Audit

**Files:**
- Verify: all four files changed by Tasks 2-3.
- Verify unchanged: `mkdocs.yml`, `src/gpconfig/**`, `tests/**`, `__version__`, `dev_docs/**`, README.

**Interfaces:**
- Consumes: all doc edits from Tasks 2-3.
- Produces: fresh evidence the docs change is complete, bilingual-parity, and scoped to the four approved files.

- [ ] **Step 1: Run the full test suite (docs must not have perturbed anything)**

```bash
.venv/Scripts/python.exe -m pytest
```

Expected: all tests pass (this should be the same count as before — the docs change touched no code/tests).

- [ ] **Step 2: Run repository-wide lint**

```bash
.venv/Scripts/python.exe -m ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 3: Re-verify the example still runs from the committed doc text**

Re-create the throwaway `.verify_example.py` from Task 1 Step 2 (same content), run it, confirm `EXAMPLE OK`, then delete it. This guards against any transcription drift between Task 1 (locked) and Task 2 (written into docs).

```bash
.venv/Scripts/python.exe .verify_example.py
rm .verify_example.py
git status --short
```

Expected: `EXAMPLE OK`; working tree clean afterward.

- [ ] **Step 4: Bilingual parity spot-check**

Confirm the four doc files contain the expected anchors and matching structure:

```bash
grep -c "## Context-Aware Construction" docs/configurable.md
grep -c "## 上下文感知构造" docs/zh/configurable.md
grep -c "context-aware-construction" docs/manager.md
grep -c "上下文感知构造" docs/zh/manager.md
```

Expected: each prints `1`.

- [ ] **Step 5: Scope check — only the four doc files changed on this branch since the docs work began**

```bash
git diff --name-only 26f3d78..HEAD
git status --short --branch
```

Expected: name list contains exactly `docs/configurable.md`, `docs/zh/configurable.md`, `docs/manager.md`, `docs/zh/manager.md`; worktree clean. (Base `26f3d78` is the docs-spec commit; everything since is the docs implementation.)

- [ ] **Step 6: Confirm version and untouched files remain untouched**

```bash
git diff main...HEAD -- mkdocs.yml README.md src/gpconfig/__init__.py dev_docs
grep -n '__version__ = "0.3.4"' src/gpconfig/__init__.py
```

Expected: the `mkdocs.yml`/`README`/`dev_docs` diff is empty; `src/gpconfig/__init__.py` shows no version-relevant change in the diff (only possibly context if it had changed — it should not); the grep prints the unchanged `0.3.4` line.

Do NOT create another commit in this task unless verification reveals a defect. If a defect is found, return to the task that owns it, fix minimally, rerun that task's focused verification, and commit the correction with the same Conventional Commit prefix as the owning task.
