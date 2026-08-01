# Reject Duplicate YAML Keys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject duplicate explicit keys in every YAML mapping loaded by gpconfig, preserve safe loading and legal merge/alias behavior, document the error contract, and release the fix as version 0.3.5.

**Architecture:** Add a private `yaml.SafeLoader` subclass in `src/gpconfig/_yaml.py` that overrides `construct_mapping()` to compare explicit keys before ordinary dictionary construction, then delegates to PyYAML's existing safe implementation. Route the single `GPConfigManager._load_yaml_dict()` parse call through this loader so normal configs, nested mappings, sequence elements, and `global_env.yaml` share the same validation and existing `ConfigValidationError` wrapper.

**Tech Stack:** Python >=3.10, PyYAML >=6.0, Pydantic 2, pytest, Ruff, MkDocs Material/static-i18n, Hatch dynamic versioning

**Design:** `docs/superpowers/specs/2026-08-02-reject-duplicate-yaml-keys-design.md`

## Global Constraints

- Perform all work on the existing `reject-duplicate-yaml-keys` branch in the current checkout; no separate worktree is required.
- Run every Python command through `.venv\Scripts\python.exe`; never use bare `python`, `pip`, `pytest`, or `ruff`.
- Keep `PyYAML>=6.0`; do not add or replace YAML dependencies.
- The custom loader must inherit `yaml.SafeLoader` and must not mutate PyYAML's global loader registrations.
- Reject duplicate explicit keys after SafeLoader resolution, including resolved-equal spellings such as `1`/`true` and `null`/`~`.
- Preserve legal YAML merge-key overrides and recursive anchor/alias mappings.
- Keep the public exception type `ConfigValidationError`, with the YAML error preserved on both `.original_error` and `.__cause__`.
- Do not add a compatibility flag, public exception type, cache behavior, save behavior, or Portfolio-specific code.
- Keep `docs/` and `docs/zh/` synchronized.
- Set the version only in `src/gpconfig/__init__.py`; `pyproject.toml` must remain unchanged.

## File Map

- Create `src/gpconfig/_yaml.py`: own the duplicate-aware safe loader and the `load_yaml(stream: TextIO) -> Any` entry point.
- Modify `src/gpconfig/manager.py:8-20,273-312`: import `load_yaml`, use it in `_load_yaml_dict()`, and describe duplicate-key validation in the helper docstring.
- Modify `tests/test_yaml_loading.py:7-112`: add end-to-end regression coverage at `_load_yaml_dict()` and manager-initialization boundaries.
- Modify `docs/exceptions.md:280-310` and `docs/zh/exceptions.md:280-310`: document duplicate-key triggers, diagnostics, and exception chaining.
- Modify `docs/manager.md:296-326` and `docs/zh/manager.md:293-323`: update the `get_config()` error contract in both languages.
- Modify `CHANGELOG.md:8-10,58-60`: add the 0.3.5 release notes and comparison links.
- Modify `src/gpconfig/__init__.py:33`: bump the single version source to 0.3.5.

---

### Task 1: Implement Duplicate-Aware Safe YAML Loading

**Files:**
- Create: `src/gpconfig/_yaml.py`
- Modify: `src/gpconfig/manager.py:8-20,273-312`
- Test: `tests/test_yaml_loading.py:7-112`

**Interfaces:**
- Consumes: PyYAML's `yaml.SafeLoader.construct_mapping(node, deep=False)`, `yaml.nodes.MappingNode`, and the existing `GPConfigManager._load_yaml_dict(file_path: Path, path_for_error: str) -> dict` exception boundary.
- Produces: `load_yaml(stream: TextIO) -> Any`; duplicate explicit keys raise `yaml.constructor.ConstructorError`, while legal input returns the same Python objects as `yaml.safe_load()`.

- [ ] **Step 1: Add failing regression tests for duplicate-key detection and compatibility**

Add `import yaml` to the imports in `tests/test_yaml_loading.py`, then insert this class between `TestLoadYamlDictDirect` and `TestGetConfigYamlTypeValidation`:

```python
class TestDuplicateYamlKeys:
    """Reject duplicate explicit keys without changing legal YAML behavior."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> GPConfigManager:
        """Create a manager whose global environment is valid."""
        (tmp_path / "global_env.yaml").write_text(
            "debug: true\n", encoding="utf-8"
        )
        return GPConfigManager("testproject", cfg_folder=tmp_path)

    def test_duplicate_top_level_key_reports_both_locations(
        self, manager: GPConfigManager, tmp_path: Path
    ):
        """Duplicate keys report the file, key, and both source locations."""
        config_file = tmp_path / "portfolio.yaml"
        config_file.write_text(
            "weight_mode: none\nweight_mode: explicit\n", encoding="utf-8"
        )

        with pytest.raises(ConfigValidationError) as exc_info:
            manager._load_yaml_dict(config_file, "portfolio")

        error = exc_info.value
        assert isinstance(error.original_error, yaml.YAMLError)
        assert error.__cause__ is error.original_error
        message = str(error)
        assert str(config_file) in message
        assert "'weight_mode'" in message
        assert "first defined here" in message
        assert "line 1, column 1" in message
        assert "repeated here" in message
        assert "line 2, column 1" in message

    @pytest.mark.parametrize(
        ("content", "duplicate_key"),
        [
            (
                "portfolio:\n"
                "  weight_mode: none\n"
                "  weight_mode: explicit\n",
                "weight_mode",
            ),
            (
                "portfolio:\n"
                "  components:\n"
                "    - symbol: 600000.XSHG\n"
                "      symbol: 000001.XSHE\n",
                "symbol",
            ),
        ],
        ids=["nested-mapping", "mapping-in-list"],
    )
    def test_duplicate_nested_keys_are_rejected(
        self,
        manager: GPConfigManager,
        tmp_path: Path,
        content: str,
        duplicate_key: str,
    ):
        """Mappings at arbitrary nesting depth use the duplicate check."""
        config_file = tmp_path / "nested.yaml"
        config_file.write_text(content, encoding="utf-8")

        with pytest.raises(ConfigValidationError) as exc_info:
            manager._load_yaml_dict(config_file, "nested")

        assert duplicate_key in str(exc_info.value)

    def test_duplicate_global_env_key_is_rejected(self, tmp_path: Path):
        """Manager initialization validates duplicate keys in global_env.yaml."""
        global_env_file = tmp_path / "global_env.yaml"
        global_env_file.write_text(
            "mode: development\nmode: production\n", encoding="utf-8"
        )

        with pytest.raises(ConfigValidationError) as exc_info:
            GPConfigManager("testproject", cfg_folder=tmp_path)

        error = exc_info.value
        assert error.path == str(global_env_file)
        assert str(global_env_file) in str(error)
        assert isinstance(error.__cause__, yaml.YAMLError)

    def test_duplicate_unicode_key_is_rejected(
        self, manager: GPConfigManager, tmp_path: Path
    ):
        """Unicode duplicate keys remain readable in the diagnostic."""
        config_file = tmp_path / "unicode.yaml"
        config_file.write_text("名称: 第一个\n名称: 第二个\n", encoding="utf-8")

        with pytest.raises(ConfigValidationError) as exc_info:
            manager._load_yaml_dict(config_file, "unicode")

        assert "名称" in str(exc_info.value)

    @pytest.mark.parametrize(
        "content",
        [
            "1: integer\ntrue: boolean\n",
            "null: first\n~: second\n",
        ],
        ids=["integer-and-boolean", "null-spellings"],
    )
    def test_resolved_equal_keys_are_rejected(
        self, manager: GPConfigManager, tmp_path: Path, content: str
    ):
        """Different source spellings that become equal dict keys are duplicates."""
        config_file = tmp_path / "resolved-equal.yaml"
        config_file.write_text(content, encoding="utf-8")

        with pytest.raises(ConfigValidationError):
            manager._load_yaml_dict(config_file, "resolved-equal")

    def test_same_key_in_different_mappings_is_allowed(
        self, manager: GPConfigManager, tmp_path: Path
    ):
        """Duplicate detection is scoped to one mapping node."""
        config_file = tmp_path / "separate.yaml"
        config_file.write_text(
            "portfolio_a:\n"
            "  weight_mode: none\n"
            "portfolio_b:\n"
            "  weight_mode: explicit\n",
            encoding="utf-8",
        )

        result = manager._load_yaml_dict(config_file, "separate")

        assert result == {
            "portfolio_a": {"weight_mode": "none"},
            "portfolio_b": {"weight_mode": "explicit"},
        }

    def test_merge_key_explicit_override_is_preserved(
        self, manager: GPConfigManager, tmp_path: Path
    ):
        """An explicit key may legally override a merged default."""
        config_file = tmp_path / "merge.yaml"
        config_file.write_text(
            "defaults: &defaults\n"
            "  host: localhost\n"
            "  port: 5432\n"
            "service:\n"
            "  <<: *defaults\n"
            "  port: 6432\n",
            encoding="utf-8",
        )

        result = manager._load_yaml_dict(config_file, "merge")

        assert result == {
            "defaults": {"host": "localhost", "port": 5432},
            "service": {"host": "localhost", "port": 6432},
        }

    def test_recursive_alias_mapping_is_preserved(
        self, manager: GPConfigManager, tmp_path: Path
    ):
        """The SafeLoader generator still supports recursive aliases."""
        config_file = tmp_path / "recursive.yaml"
        config_file.write_text(
            "root: &root\n"
            "  name: recursive\n"
            "  self: *root\n",
            encoding="utf-8",
        )

        result = manager._load_yaml_dict(config_file, "recursive")

        root = result["root"]
        assert root["self"] is root

    def test_global_pyyaml_safe_loader_is_unchanged(self):
        """The private loader does not mutate yaml.SafeLoader registrations."""
        result = yaml.safe_load("key: first\nkey: second\n")

        assert result == {"key": "second"}
```

- [ ] **Step 2: Run the YAML-loading tests and confirm the duplicate cases fail**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_yaml_loading.py -v
```

Expected: the new duplicate-key tests fail with `DID NOT RAISE <class 'gpconfig.exceptions.ConfigValidationError'>`; the same-mapping-scope, merge, and recursive-alias compatibility tests pass.

- [ ] **Step 3: Create the private duplicate-aware SafeLoader**

Create `src/gpconfig/_yaml.py` with this complete implementation:

```python
"""Safe YAML loading helpers for gpconfig."""

from collections.abc import Hashable
from typing import Any, TextIO

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, Node

_YAML_MERGE_TAG = "tag:yaml.org,2002:merge"


class _RejectDuplicateKeysSafeLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate explicit keys in each mapping."""

    def construct_mapping(
        self, node: Node, deep: bool = False
    ) -> dict[Any, Any]:
        """Construct a mapping after rejecting duplicate explicit keys."""
        if not isinstance(node, MappingNode):
            return super().construct_mapping(node, deep=deep)

        explicit_key_nodes = [
            key_node
            for key_node, _ in node.value
            if key_node.tag != _YAML_MERGE_TAG
        ]
        self.flatten_mapping(node)

        seen: dict[Any, Node] = {}
        for key_node in explicit_key_nodes:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                continue
            if key in seen:
                first_key_node = seen[key]
                raise ConstructorError(
                    f"while constructing a mapping; key {key!r} first defined here",
                    first_key_node.start_mark,
                    f"found duplicate key {key!r}; repeated here",
                    key_node.start_mark,
                )
            seen[key] = key_node

        return super().construct_mapping(node, deep=deep)


def load_yaml(stream: TextIO) -> Any:
    """Load YAML safely while rejecting duplicate explicit mapping keys.

    Args:
        stream: Text stream containing one YAML document.

    Returns:
        The Python object constructed by PyYAML's safe constructors.

    Raises:
        yaml.YAMLError: If the YAML is malformed or contains duplicate explicit
            keys in one mapping.
    """
    return yaml.load(stream, Loader=_RejectDuplicateKeysSafeLoader)
```

This method override deliberately retains the inherited generator-based
`construct_yaml_map()` registration. Do not replace the default mapping-tag
constructor with a direct-return function; doing so breaks recursive aliases.

- [ ] **Step 4: Route `_load_yaml_dict()` through the private loader**

In `src/gpconfig/manager.py`, keep `import yaml` for the existing
`except yaml.YAMLError` clause and add this absolute import with the other
gpconfig imports:

```python
from gpconfig._yaml import load_yaml
```

Replace the parse call inside `_load_yaml_dict()`:

```python
raw_data = load_yaml(f)
```

Update the `ConfigValidationError` entry in the method's `Raises:` section to:

```python
            ConfigValidationError: If YAML parsing fails, a mapping contains
                duplicate explicit keys, or the top-level YAML value is not a
                dict (e.g. a list or scalar).
```

Leave the existing file opening, error wrapping, empty-document handling, and
top-level type validation unchanged.

- [ ] **Step 5: Run focused tests and confirm every YAML-loading case passes**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_yaml_loading.py -v
```

Expected: `23 passed`; the duplicate-key diagnostics include both marks, the
merge and recursive-alias identity tests remain green, and direct
`yaml.safe_load()` behavior is unchanged.

- [ ] **Step 6: Lint the implementation files**

Run:

```powershell
.venv\Scripts\python.exe -m ruff check src/gpconfig/_yaml.py src/gpconfig/manager.py tests/test_yaml_loading.py
```

Expected: `All checks passed!`

- [ ] **Step 7: Commit the tested loader, integration, and regressions**

```powershell
git add -- src/gpconfig/_yaml.py src/gpconfig/manager.py tests/test_yaml_loading.py
git commit -m "fix: reject duplicate YAML mapping keys"
```

### Task 2: Document the Error Contract and 0.3.5 Change

**Files:**
- Modify: `docs/exceptions.md:280-310`
- Modify: `docs/zh/exceptions.md:280-310`
- Modify: `docs/manager.md:296-326`
- Modify: `docs/zh/manager.md:293-323`
- Modify: `CHANGELOG.md:8-10,58-60`

**Interfaces:**
- Consumes: Task 1's `ConfigValidationError -> ConstructorError` chain and duplicate-key message fields.
- Produces: Synchronized English/Chinese user documentation and a dated 0.3.5 changelog entry; Task 3 relies on this release entry before changing `__version__`.

- [ ] **Step 1: Update the English `ConfigValidationError` reference**

In `docs/exceptions.md`, add this trigger immediately after the existing YAML
syntax/parse-error bullet:

```markdown
- **Duplicate explicit YAML key** — two keys in the same mapping resolve to the same Python dictionary key, including differently written keys such as `1`/`true` or `null`/`~`. The original error is a `yaml.constructor.ConstructorError`; its message identifies the key, file path, first definition line/column, and repeated line/column. The same key may still appear in separate mappings, and explicit keys may override values supplied through a legal merge key (`<<`).
```

Replace the paragraph beginning `In all cases` with:

```markdown
In all cases the exception message carries the **dotted config path** (on `.path`), the **on-disk file path**, and the underlying error's detail. Duplicate-key errors additionally carry the readable key plus the first and repeated line/column locations. YAML errors are preserved on both `.original_error` and `.__cause__`, so callers can inspect the original `yaml.YAMLError` without parsing the wrapper's complete message.
```

- [ ] **Step 2: Apply the equivalent Chinese exception documentation**

In `docs/zh/exceptions.md`, add this trigger immediately after the YAML
syntax/parse-error bullet:

```markdown
- **YAML 显式键重复** —— 同一个 mapping 中的两个键解析成相同的 Python 字典键，包括 `1`/`true`、`null`/`~` 等写法不同但解析结果相等的键。原始错误为 `yaml.constructor.ConstructorError`；其消息会指出重复键、文件路径、首次定义的行列号，以及重复定义的行列号。同名键仍可分别出现在不同 mapping 中，显式键也仍可覆盖合法 merge key（`<<`）提供的值。
```

Replace the paragraph beginning `无论哪种情况` with:

```markdown
无论哪种情况，异常消息都携带**点分配置路径**（`.path`）、**磁盘上的文件路径**，以及底层错误的详细信息。重复键错误还会携带可读的键名、首次定义的行列号和重复定义的行列号。YAML 错误会同时保存在 `.original_error` 与 `.__cause__` 上，调用方无需解析包装异常的完整文本即可检查原始 `yaml.YAMLError`。
```

- [ ] **Step 3: Update the English and Chinese manager references**

Replace the `ConfigValidationError` bullet under `get_config()` in
`docs/manager.md` with:

```markdown
- `ConfigValidationError` if the YAML file has a syntax error, contains duplicate explicit keys in one mapping, has a non-dict top level, or fails Pydantic validation. Duplicate-key diagnostics include the key, on-disk file path, and first/repeated line and column; the underlying YAML error is preserved on both `.original_error` and `.__cause__`.
```

Replace the matching bullet in `docs/zh/manager.md` with:

```markdown
- 当 YAML 文件存在语法错误、同一个 mapping 中包含重复显式键、顶层不是字典，或未通过 Pydantic 校验时抛出 `ConfigValidationError`。重复键诊断包含键名、磁盘文件路径，以及首次/重复定义的行列号；底层 YAML 错误同时保存在 `.original_error` 和 `.__cause__` 上。
```

- [ ] **Step 4: Add the 0.3.5 changelog entry and comparison links**

Insert this section after `## [Unreleased]` in `CHANGELOG.md`:

```markdown
## [0.3.5] - 2026-08-02

**Duplicate YAML key validation bugfix release.** gpconfig now fails early
instead of silently accepting mappings whose later key overwrites an earlier
key during PyYAML construction. Public loading APIs and exception types remain
unchanged.

### Fixed
- All mappings loaded through `GPConfigManager._load_yaml_dict()` now reject duplicate explicit keys before conversion to `dict`, including nested mappings, mappings inside lists, `global_env.yaml`, Unicode keys, and differently written keys that resolve to equal Python values.
- Duplicate-key failures surface as `ConfigValidationError` chained from `yaml.constructor.ConstructorError`; diagnostics include the file path, readable key, first definition line/column, and repeated line/column.
- The private loader remains a `yaml.SafeLoader` subclass and preserves legal merge-key overrides, recursive aliases, empty/comment-only files, non-mapping validation, and existing valid YAML results.

### Documentation
- Documented duplicate-key validation and its exception-chain contract in the English and Chinese exception and manager references.
```

Replace the changelog comparison links with:

```markdown
[Unreleased]: https://github.com/LinnetCodes/gpconfig/compare/version-0.3.5...HEAD
[0.3.5]: https://github.com/LinnetCodes/gpconfig/compare/version-0.3.4...version-0.3.5
[0.3.4]: https://github.com/LinnetCodes/gpconfig/releases/tag/version-0.3.4
[0.3.3]: https://github.com/LinnetCodes/gpconfig/releases/tag/version-0.3.3
```

- [ ] **Step 5: Validate Markdown formatting and build both documentation languages**

Run:

```powershell
git diff --check
.venv\Scripts\python.exe -m mkdocs build --strict
```

Expected: `git diff --check` prints nothing, and MkDocs completes with no errors
or warnings. Confirm `git status --short` shows only the five intended tracked
documentation/changelog files; generated `site/` output must remain ignored.

- [ ] **Step 6: Commit the synchronized documentation and changelog**

```powershell
git add -- docs/exceptions.md docs/zh/exceptions.md docs/manager.md docs/zh/manager.md CHANGELOG.md
git commit -m "docs: document duplicate YAML key validation"
```

### Task 3: Bump to 0.3.5 and Run Release Verification

**Files:**
- Modify: `src/gpconfig/__init__.py:33`

**Interfaces:**
- Consumes: Task 1's tested loader behavior and Task 2's dated 0.3.5 changelog entry.
- Produces: `gpconfig.__version__ == "0.3.5"` through the existing Hatch dynamic-version source; no `pyproject.toml` change.

- [ ] **Step 1: Change the single version source**

In `src/gpconfig/__init__.py`, replace:

```python
__version__ = "0.3.4"
```

with:

```python
__version__ = "0.3.5"
```

- [ ] **Step 2: Verify the installed editable package reports 0.3.5**

Run:

```powershell
.venv\Scripts\python.exe -c "import gpconfig; assert gpconfig.__version__ == '0.3.5'; print(gpconfig.__version__)"
```

Expected output: `0.3.5`.

- [ ] **Step 3: Run the complete release verification suite**

Run each command independently and stop on the first failure:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mkdocs build --strict
git diff --check
```

Expected: the full pytest suite passes, Ruff reports `All checks passed!`,
MkDocs builds without errors or warnings, and `git diff --check` prints nothing.

- [ ] **Step 4: Confirm the final diff contains only the approved release scope**

Run:

```powershell
git status --short
git diff --stat HEAD~2
git diff -- src/gpconfig/__init__.py
```

Expected: before the version commit, only `src/gpconfig/__init__.py` is
uncommitted; the cumulative implementation diff contains the loader,
manager integration, YAML tests, synchronized EN/ZH docs, changelog, and
version bump, with no `pyproject.toml`, README, dependency, cache, or save-path
changes.

- [ ] **Step 5: Commit the version bump**

```powershell
git add -- src/gpconfig/__init__.py
git commit -m "chore: bump version to 0.3.5"
```

- [ ] **Step 6: Verify the branch is clean and contains the three planned implementation commits**

Run:

```powershell
git status --short --branch
git log -5 --oneline --decorate
```

Expected: the branch is clean. The newest implementation commits are, in
order, `chore: bump version to 0.3.5`,
`docs: document duplicate YAML key validation`, and
`fix: reject duplicate YAML mapping keys`, following the already committed
design and implementation-plan documents.
