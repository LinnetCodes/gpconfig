# Context-Aware Object Construction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit, immutable construction context to `GPConfigurable` object creation while enforcing the documented configurable-class registration contract and preserving standard `GPConfigurable(config)` subclasses.

**Architecture:** Define the public context, default construction hook, and dedicated contract exception beside the existing configurable API. Make `GPConfigManager` validate registrations, derive a canonical dotted path from the resolved YAML file, invoke the hook exactly once, and validate its return value; keep `GPConfigFolder` as a pure delegating wrapper. Record the two intentional breaking changes in a new migration guide without changing existing published documentation.

**Tech Stack:** Python 3.10+, Pydantic 2, PyYAML 6, pytest, pytest-cov, Ruff, Hatchling.

## Global Constraints

- Run every Python command with `.venv/Scripts/python.exe`; never use bare `python`, `pip`, `pytest`, or `ruff`.
- Keep Python support at `>=3.10`; use a bound `TypeVar`, not `typing.Self`.
- Add no runtime or development dependencies.
- Keep `GPConfig` free of manager, context, and canonical-path fields.
- Do not change YAML schema, `cfg_class_name`, `configured_class_name`, save formatting, configuration caching, folder resolution, or object non-caching semantics.
- `register_configurable_class()` must accept only classes that subclass `GPConfigurable`; do not inspect `from_config()` signatures.
- Call `from_config(config, context=context)` exactly once; propagate hook exceptions unchanged and never retry `configurable_cls(config)` after failure.
- Modify no existing files under `docs/` or `docs/zh/`, no README, no `mkdocs.yml`, no version number, and no release workflow.
- The only feature-facing document added during implementation is `dev_docs/gpconfig-context-aware-object-construction-migration-guide.md`.
- Work and commit only on `context-aware-object-construction-refactor`.

---

## File Structure

### Source files

- Modify `src/gpconfig/configurable.py`: own `GPConfigurableContext`, the Python-3.10-compatible bound type variable, and the default `GPConfigurable.from_config()` hook.
- Modify `src/gpconfig/exceptions.py`: own `ConfigurableConstructionError` and its structured attributes.
- Modify `src/gpconfig/manager.py`: enforce registration type safety, canonicalize object paths, invoke the hook, and validate the returned object.
- Modify `src/gpconfig/__init__.py`: expose the new context and exception from the package root.

No new source module is needed: context and hook are one construction-boundary responsibility and belong together in `configurable.py`.

### Test files

- Modify `tests/test_configurable.py`: verify the immutable/slotted context and default legacy constructor path.
- Modify `tests/test_exceptions.py`: verify exception hierarchy, attributes, and diagnostic message.
- Modify `tests/test_exports.py`: verify root imports and `__all__` entries.
- Modify `tests/test_manager_objects.py`: verify registration enforcement, context data flow, canonical paths, cache reuse, manager isolation, fail-fast behavior, result validation, and no config pollution.
- Modify `tests/test_gpconfig_folder.py`: verify folder-prefixed context delegation.

### New documentation

- Create `dev_docs/gpconfig-context-aware-object-construction-migration-guide.md`: explain the two breaking changes and concrete adaptations.

---

### Task 1: Public Construction Contracts

**Files:**
- Modify: `src/gpconfig/configurable.py:1-31`
- Modify: `src/gpconfig/exceptions.py:39-51`
- Modify: `src/gpconfig/__init__.py:4-30`
- Test: `tests/test_configurable.py:1-55`
- Test: `tests/test_exceptions.py:1-70`
- Test: `tests/test_exports.py:5-49`

**Interfaces:**
- Consumes: existing `GPConfigurable.__init__(config: GPConfig) -> None`.
- Produces: `GPConfigurableContext(manager: GPConfigManager, path: str)`; `GPConfigurable.from_config(config: GPConfig, *, context: GPConfigurableContext) -> GPConfigurableT`; `ConfigurableConstructionError(path: str, expected_type: type, actual_type: type)`.

- [ ] **Step 1: Confirm the implementation workspace is the requested clean branch**

Run:

```powershell
git branch --show-current
git status --short
```

Expected: branch output is `context-aware-object-construction-refactor`; status has no uncommitted files.

- [ ] **Step 2: Run the baseline suite before implementation**

Run:

```powershell
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m ruff check .
```

Expected: all existing tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 3: Add failing tests for the immutable context and default hook**

Update the imports and append this test class to `tests/test_configurable.py`:

```python
from dataclasses import FrozenInstanceError

import pytest

from gpconfig.config import GPConfig
from gpconfig.configurable import GPConfigurable, GPConfigurableContext


class TestGPConfigurableConstruction:
    """Test the public configurable construction contracts."""

    def test_context_is_frozen_and_slotted(self):
        manager = object()
        context = GPConfigurableContext(manager=manager, path="services.api")

        assert context.manager is manager
        assert context.path == "services.api"
        assert not hasattr(context, "__dict__")
        with pytest.raises(FrozenInstanceError):
            context.path = "services.worker"

    def test_default_from_config_calls_legacy_constructor(self):
        config = MockConfig(value="legacy", count=7)
        context = GPConfigurableContext(manager=object(), path="mock")

        obj = MockConfigurable.from_config(config, context=context)

        assert isinstance(obj, MockConfigurable)
        assert obj.config is config
        assert obj.value == "legacy"
        assert obj.count == 7
```

- [ ] **Step 4: Add failing tests for the construction exception**

Add `ConfigurableConstructionError` to the import list in `tests/test_exceptions.py`, then add:

```python
class TestConfigurableConstructionError:
    """Test construction contract violation details."""

    def test_is_gpconfig_error(self):
        assert issubclass(ConfigurableConstructionError, GPConfigError)

    def test_stores_contract_details(self):
        class ExpectedConfigurable:
            pass

        error = ConfigurableConstructionError(
            "services.api",
            ExpectedConfigurable,
            dict,
        )

        assert error.path == "services.api"
        assert error.expected_type is ExpectedConfigurable
        assert error.actual_type is dict
        assert "ExpectedConfigurable" in str(error)
        assert "services.api" in str(error)
        assert "dict" in str(error)
```

- [ ] **Step 5: Add failing root-export tests**

Add this method to `TestPublicAPI` in `tests/test_exports.py`:

```python
def test_export_construction_contracts(self):
    from gpconfig import ConfigurableConstructionError, GPConfigurableContext

    assert GPConfigurableContext is not None
    assert ConfigurableConstructionError is not None
```

Add both names to the `expected` set in `test_all_exports_in_dunder_all()`:

```python
"GPConfigurableContext",
"ConfigurableConstructionError",
```

- [ ] **Step 6: Run the new tests and verify the missing APIs fail collection**

Run:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_configurable.py tests/test_exceptions.py tests/test_exports.py -v
```

Expected: FAIL during collection because `GPConfigurableContext` and `ConfigurableConstructionError` cannot yet be imported.

- [ ] **Step 7: Implement `GPConfigurableContext` and the default hook**

Replace the imports and type-checking block at the top of `src/gpconfig/configurable.py` with:

```python
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from gpconfig.config import GPConfig
    from gpconfig.manager import GPConfigManager


@dataclass(frozen=True, slots=True)
class GPConfigurableContext:
    """Immutable dependencies for constructing a configurable object.

    Attributes:
        manager: Manager that received the object-construction request.
        path: Canonical dotted path of the source YAML file.
    """

    manager: "GPConfigManager"
    path: str


GPConfigurableT = TypeVar("GPConfigurableT", bound="GPConfigurable")
```

Add this method to `GPConfigurable` immediately after `__init__`:

```python
@classmethod
def from_config(
    cls: type[GPConfigurableT],
    config: "GPConfig",
    *,
    context: GPConfigurableContext,
) -> GPConfigurableT:
    """Construct an object from config within a manager context.

    Args:
        config: Configuration instance for the object.
        context: Manager and canonical path for this construction request.

    Returns:
        A newly constructed instance of the configurable subclass.
    """
    return cls(config)
```

- [ ] **Step 8: Implement the dedicated contract exception**

Add this class after `RegistrationError` in `src/gpconfig/exceptions.py`:

```python
class ConfigurableConstructionError(GPConfigError):
    """Raised when a construction hook returns an invalid object type.

    Attributes:
        path: Canonical dotted path used for object construction.
        expected_type: Registered configurable class that should be returned.
        actual_type: Type actually returned by the construction hook.
    """

    def __init__(
        self,
        path: str,
        expected_type: type,
        actual_type: type,
    ) -> None:
        """Initialize a construction contract error.

        Args:
            path: Canonical dotted path used for object construction.
            expected_type: Registered configurable class expected from the hook.
            actual_type: Type actually returned by the hook.
        """
        self.path = path
        self.expected_type = expected_type
        self.actual_type = actual_type
        super().__init__(
            f"Configurable '{expected_type.__name__}' from path '{path}' returned "
            f"{actual_type.__name__}; expected an instance of "
            f"{expected_type.__name__}"
        )
```

- [ ] **Step 9: Export the new public APIs**

Update `src/gpconfig/__init__.py` to import both configurable classes:

```python
from gpconfig.configurable import GPConfigurable, GPConfigurableContext
```

Add `ConfigurableConstructionError` to the exception import block. Add these entries to `__all__` in their respective sections:

```python
"GPConfigurableContext",
"ConfigurableConstructionError",
```

Do not change `__version__`.

- [ ] **Step 10: Run focused tests and lint**

Run:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_configurable.py tests/test_exceptions.py tests/test_exports.py -v
.venv/Scripts/python.exe -m ruff check src/gpconfig/configurable.py src/gpconfig/exceptions.py src/gpconfig/__init__.py tests/test_configurable.py tests/test_exceptions.py tests/test_exports.py
```

Expected: all focused tests pass and Ruff reports no errors.

- [ ] **Step 11: Commit the public contracts**

```powershell
git add -- src/gpconfig/configurable.py src/gpconfig/exceptions.py src/gpconfig/__init__.py tests/test_configurable.py tests/test_exceptions.py tests/test_exports.py
git commit -m "feat: add configurable construction contracts"
```

---

### Task 2: Enforce Configurable Registration Type Safety

**Files:**
- Modify: `src/gpconfig/manager.py:1-20,107-110,688-709`
- Test: `tests/test_manager_objects.py:160-186`

**Interfaces:**
- Consumes: `GPConfigurable` from Task 1.
- Produces: `GPConfigManager.register_configurable_class(configurable_cls: type[GPConfigurable]) -> None`, with runtime subclass validation and unchanged idempotency/name-conflict rules.

- [ ] **Step 1: Add failing tests for non-class and non-subclass registrations**

Append these tests to `TestRegisterConfigurableClassSingleParam` in `tests/test_manager_objects.py`:

```python
def test_register_non_class_raises_without_mutating_registry(self):
    with pytest.raises(RegistrationError) as exc_info:
        GPConfigManager.register_configurable_class(object())

    assert "GPConfigurable subclass" in str(exc_info.value)
    assert GPConfigManager._configurable_classes == {}

def test_register_non_subclass_raises_without_mutating_registry(self):
    class DuckTypedDatabase:
        def __init__(self, config: DatabaseConfig) -> None:
            self.config = config

    with pytest.raises(RegistrationError) as exc_info:
        GPConfigManager.register_configurable_class(DuckTypedDatabase)

    assert "GPConfigurable subclass" in str(exc_info.value)
    assert GPConfigManager._configurable_classes == {}
```

- [ ] **Step 2: Run the registration tests and verify both new cases fail**

Run:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_manager_objects.py::TestRegisterConfigurableClassSingleParam -v
```

Expected: FAIL; the object instance raises `AttributeError` instead of `RegistrationError`, and the duck-typed class is currently accepted.

- [ ] **Step 3: Add the runtime subclass check and tighten registry types**

Add the runtime import in `src/gpconfig/manager.py`:

```python
from gpconfig.configurable import GPConfigurable
```

Change the configurable registry annotation to:

```python
_configurable_classes: dict[str, type[GPConfigurable]] = {}
```

Replace `register_configurable_class()` with:

```python
@classmethod
def register_configurable_class(
    cls,
    configurable_cls: type[GPConfigurable],
) -> None:
    """Register a GPConfigurable subclass by its class name.

    Args:
        configurable_cls: The GPConfigurable subclass to register.

    Raises:
        RegistrationError: If configurable_cls is not a GPConfigurable
            subclass, or if a different class has the same name.
    """
    if not isinstance(configurable_cls, type) or not issubclass(
        configurable_cls, GPConfigurable
    ):
        raise RegistrationError(
            "Configurable class must be a GPConfigurable subclass, "
            f"got {configurable_cls!r}"
        )

    class_name = configurable_cls.__name__
    if class_name in cls._configurable_classes:
        if cls._configurable_classes[class_name] is configurable_cls:
            return
        raise RegistrationError(
            f"Configurable class name '{class_name}' is already registered "
            "with a different class"
        )
    cls._configurable_classes[class_name] = configurable_cls
```

Do not inspect the hook signature and do not modify `register_config_class()`.

- [ ] **Step 4: Run the complete manager-object tests and lint**

Run:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_manager_objects.py -v
.venv/Scripts/python.exe -m ruff check src/gpconfig/manager.py tests/test_manager_objects.py
```

Expected: all existing registration, idempotency, conflict, reset, and object tests pass together with the two new rejection tests.

- [ ] **Step 5: Commit registration enforcement**

```powershell
git add -- src/gpconfig/manager.py tests/test_manager_objects.py
git commit -m "feat: require GPConfigurable registration"
```

---

### Task 3: Construct Objects Through Context-Aware Hooks

**Files:**
- Modify: `src/gpconfig/manager.py:1-20,429-466,724-772`
- Modify: `tests/test_manager_objects.py:1-99,240-291`
- Modify: `tests/test_gpconfig_folder.py:1-116`

**Interfaces:**
- Consumes: `GPConfigurableContext`, `ConfigurableConstructionError`, and the validated `type[GPConfigurable]` registry from Tasks 1-2.
- Produces: `GPConfigManager._canonical_config_path(path: str) -> str`; one-shot dispatch to `configurable_cls.from_config(config, *, context)`; return validation with `isinstance(result, configurable_cls)`.

- [ ] **Step 1: Add a reusable context-capturing configurable to manager tests**

Update the imports in `tests/test_manager_objects.py`:

```python
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

from gpconfig.config import GPConfig
from gpconfig.configurable import GPConfigurable, GPConfigurableContext
from gpconfig.exceptions import (
    ConfigNotFoundError,
    ConfigurableConstructionError,
    RegistrationError,
)
from gpconfig.manager import GPConfigManager
```

Add this class after `Database`:

```python
class ContextAwareDatabase(Database):
    """Database that records every manager construction context."""

    received_contexts: ClassVar[list[GPConfigurableContext]] = []

    @classmethod
    def from_config(
        cls,
        config: DatabaseConfig,
        *,
        context: GPConfigurableContext,
    ) -> "ContextAwareDatabase":
        cls.received_contexts.append(context)
        return cls(config)
```

Clear the test-only state in the existing autouse fixture:

```python
@pytest.fixture(autouse=True)
def reset_registry():
    """Reset class-level registries and construction observations."""
    GPConfigManager.reset_registries()
    ContextAwareDatabase.received_contexts.clear()
    yield
    GPConfigManager.reset_registries()
    ContextAwareDatabase.received_contexts.clear()
```

- [ ] **Step 2: Add failing manager identity, canonical-path, and non-caching tests**

Add these methods to `TestGetObject`:

```python
def test_get_object_passes_original_manager_and_canonical_path(
    self,
    manager_with_configs,
):
    config_file = manager_with_configs.cfg_folder / "database.yaml"
    config_file.write_text(
        "cfg_class_name: 'TestObjectsDatabaseConfig'\n"
        "configured_class_name: 'ContextAwareDatabase'\n"
        "host: localhost\n"
        "port: 5432\n",
        encoding="utf-8",
    )
    GPConfigManager.register_config_class(DatabaseConfig)
    GPConfigManager.register_configurable_class(ContextAwareDatabase)

    first = manager_with_configs.get_object("database")
    second = manager_with_configs.get_object("testproject.database")

    assert isinstance(first, ContextAwareDatabase)
    assert isinstance(second, ContextAwareDatabase)
    assert first is not second
    assert len(ContextAwareDatabase.received_contexts) == 2
    assert all(
        context.manager is manager_with_configs
        for context in ContextAwareDatabase.received_contexts
    )
    assert [
        context.path for context in ContextAwareDatabase.received_contexts
    ] == ["database", "database"]

def test_two_managers_receive_their_own_context(self, tmp_path: Path):
    managers = []
    for folder_name, host in (("one", "db-one"), ("two", "db-two")):
        cfg_folder = tmp_path / folder_name
        cfg_folder.mkdir()
        (cfg_folder / "global_env.yaml").write_text(
            "version: 1.0\n",
            encoding="utf-8",
        )
        (cfg_folder / "database.yaml").write_text(
            "cfg_class_name: 'TestObjectsDatabaseConfig'\n"
            "configured_class_name: 'ContextAwareDatabase'\n"
            f"host: {host}\n"
            "port: 5432\n",
            encoding="utf-8",
        )
        managers.append(GPConfigManager("testproject", cfg_folder=cfg_folder))

    GPConfigManager.register_config_class(DatabaseConfig)
    GPConfigManager.register_configurable_class(ContextAwareDatabase)

    first = managers[0].get_object("database")
    second = managers[1].get_object("database")

    assert first.config.host == "db-one"
    assert second.config.host == "db-two"
    assert ContextAwareDatabase.received_contexts[0].manager is managers[0]
    assert ContextAwareDatabase.received_contexts[1].manager is managers[1]
```

- [ ] **Step 3: Add failing same-manager dependency and cache-reuse test**

Add this method to `TestGetObject`:

```python
def test_hook_loads_related_config_through_same_manager_cache(
    self,
    manager_with_configs,
):
    class RelatedLoadingDatabase(Database):
        @classmethod
        def from_config(
            cls,
            config: DatabaseConfig,
            *,
            context: GPConfigurableContext,
        ) -> "RelatedLoadingDatabase":
            obj = cls(config)
            obj.related = context.manager.get_config("related", DatabaseConfig)
            obj.related_again = context.manager.get_config(
                "related",
                DatabaseConfig,
            )
            return obj

    (manager_with_configs.cfg_folder / "database.yaml").write_text(
        "cfg_class_name: 'TestObjectsDatabaseConfig'\n"
        "configured_class_name: 'RelatedLoadingDatabase'\n"
        "host: root\n"
        "port: 5432\n",
        encoding="utf-8",
    )
    (manager_with_configs.cfg_folder / "related.yaml").write_text(
        "host: dependency\nport: 5433\n",
        encoding="utf-8",
    )
    GPConfigManager.register_config_class(DatabaseConfig)
    GPConfigManager.register_configurable_class(RelatedLoadingDatabase)

    obj = manager_with_configs.get_object("database")

    assert obj.related.host == "dependency"
    assert obj.related is obj.related_again
```

- [ ] **Step 4: Add failing fail-fast and return-contract tests**

Add these methods to `TestGetObject`:

```python
def test_hook_exception_propagates_without_constructor_retry(
    self,
    manager_with_configs,
):
    sentinel = RuntimeError("construction failed")

    class ExplodingDatabase(Database):
        constructor_calls: ClassVar[int] = 0

        def __init__(self, config: DatabaseConfig) -> None:
            type(self).constructor_calls += 1
            super().__init__(config)

        @classmethod
        def from_config(
            cls,
            config: DatabaseConfig,
            *,
            context: GPConfigurableContext,
        ) -> "ExplodingDatabase":
            raise sentinel

    (manager_with_configs.cfg_folder / "database.yaml").write_text(
        "cfg_class_name: 'TestObjectsDatabaseConfig'\n"
        "configured_class_name: 'ExplodingDatabase'\n"
        "host: localhost\nport: 5432\n",
        encoding="utf-8",
    )
    GPConfigManager.register_config_class(DatabaseConfig)
    GPConfigManager.register_configurable_class(ExplodingDatabase)

    with pytest.raises(RuntimeError) as exc_info:
        manager_with_configs.get_object("database")

    assert exc_info.value is sentinel
    assert ExplodingDatabase.constructor_calls == 0

def test_incompatible_hook_signature_propagates_type_error_without_retry(
    self,
    manager_with_configs,
):
    class IncompatibleFactoryDatabase(Database):
        constructor_calls: ClassVar[int] = 0

        def __init__(self, config: DatabaseConfig) -> None:
            type(self).constructor_calls += 1
            super().__init__(config)

        @classmethod
        def from_config(
            cls,
            config: DatabaseConfig,
        ) -> "IncompatibleFactoryDatabase":
            return cls(config)

    (manager_with_configs.cfg_folder / "database.yaml").write_text(
        "cfg_class_name: 'TestObjectsDatabaseConfig'\n"
        "configured_class_name: 'IncompatibleFactoryDatabase'\n"
        "host: localhost\nport: 5432\n",
        encoding="utf-8",
    )
    GPConfigManager.register_config_class(DatabaseConfig)
    GPConfigManager.register_configurable_class(IncompatibleFactoryDatabase)

    with pytest.raises(TypeError, match="context"):
        manager_with_configs.get_object("database")

    assert IncompatibleFactoryDatabase.constructor_calls == 0

def test_wrong_hook_result_raises_construction_error(
    self,
    manager_with_configs,
):
    class WrongReturnDatabase(Database):
        @classmethod
        def from_config(
            cls,
            config: DatabaseConfig,
            *,
            context: GPConfigurableContext,
        ) -> object:
            return {}

    (manager_with_configs.cfg_folder / "database.yaml").write_text(
        "cfg_class_name: 'TestObjectsDatabaseConfig'\n"
        "configured_class_name: 'WrongReturnDatabase'\n"
        "host: localhost\nport: 5432\n",
        encoding="utf-8",
    )
    GPConfigManager.register_config_class(DatabaseConfig)
    GPConfigManager.register_configurable_class(WrongReturnDatabase)

    with pytest.raises(ConfigurableConstructionError) as exc_info:
        manager_with_configs.get_object("testproject.database")

    assert exc_info.value.path == "database"
    assert exc_info.value.expected_type is WrongReturnDatabase
    assert exc_info.value.actual_type is dict

def test_hook_may_return_registered_class_subclass(
    self,
    manager_with_configs,
):
    class RegisteredDatabase(Database):
        @classmethod
        def from_config(
            cls,
            config: DatabaseConfig,
            *,
            context: GPConfigurableContext,
        ) -> "RegisteredDatabase":
            return DerivedDatabase(config)

    class DerivedDatabase(RegisteredDatabase):
        pass

    (manager_with_configs.cfg_folder / "database.yaml").write_text(
        "cfg_class_name: 'TestObjectsDatabaseConfig'\n"
        "configured_class_name: 'RegisteredDatabase'\n"
        "host: localhost\nport: 5432\n",
        encoding="utf-8",
    )
    GPConfigManager.register_config_class(DatabaseConfig)
    GPConfigManager.register_configurable_class(RegisteredDatabase)

    obj = manager_with_configs.get_object("database")

    assert isinstance(obj, DerivedDatabase)
```

- [ ] **Step 5: Add the no-config-pollution and save-format regression test**

Add this method to `TestGetObject`:

```python
def test_context_is_not_attached_to_config_or_saved_yaml(
    self,
    manager_with_configs,
):
    (manager_with_configs.cfg_folder / "database.yaml").write_text(
        "cfg_class_name: 'TestObjectsDatabaseConfig'\n"
        "configured_class_name: 'ContextAwareDatabase'\n"
        "host: localhost\nport: 5432\n",
        encoding="utf-8",
    )
    GPConfigManager.register_config_class(DatabaseConfig)
    GPConfigManager.register_configurable_class(ContextAwareDatabase)

    obj = manager_with_configs.get_object("database")

    assert not hasattr(obj.config, "manager")
    assert not hasattr(obj.config, "context")
    assert not hasattr(obj.config, "path")
    obj.config.save()
    with open(obj.config.cfg_file_path, "r", encoding="utf-8") as config_file:
        saved = yaml.safe_load(config_file)
    assert {"manager", "context", "path"}.isdisjoint(saved)
```

- [ ] **Step 6: Extend the folder delegation test with context assertions**

At the top of `tests/test_gpconfig_folder.py`, import:

```python
from gpconfig.configurable import GPConfigurable, GPConfigurableContext
```

Replace the complete method body after its docstring in
`test_folder_get_object()` with the following code, removing the existing
function-local `GPConfigurable` import:

```python
class TestService(GPConfigurable):
    received_context: GPConfigurableContext | None = None

    @classmethod
    def from_config(
        cls,
        config: SampleConfig,
        *,
        context: GPConfigurableContext,
    ) -> "TestService":
        cls.received_context = context
        return cls(config)

GPConfigManager.register_config_class(SampleConfig)
GPConfigManager.register_configurable_class(TestService)

(manager_with_folder.cfg_folder / "services" / "api.yaml").write_text(
    "value: api_value\nconfigured_class_name: TestService\n",
    encoding="utf-8",
)

folder = manager_with_folder.get_config("services")
obj = folder.get_object("api")

assert isinstance(obj, TestService)
assert TestService.received_context is not None
assert TestService.received_context.manager is manager_with_folder
assert TestService.received_context.path == "services.api"
```

- [ ] **Step 7: Run the new construction tests and verify legacy direct construction fails them**

Run:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_manager_objects.py tests/test_gpconfig_folder.py -v
```

Expected: FAIL in the new context tests because current `get_object()` calls the constructor directly, never invokes the hooks, never validates wrong return values, and never records folder context.

- [ ] **Step 8: Implement canonical path derivation and one-shot hook dispatch**

Update the runtime import in `src/gpconfig/manager.py`:

```python
from gpconfig.configurable import GPConfigurable, GPConfigurableContext
```

Add `ConfigurableConstructionError` to the `gpconfig.exceptions` import block.

Add this helper immediately after `_parse_path()`:

```python
def _canonical_config_path(self, path: str) -> str:
    """Return the canonical dotted path of a resolved YAML file."""
    file_path, _ = self._parse_path(path)
    relative_path = file_path.relative_to(self._cfg_folder).with_suffix("")
    return ".".join(relative_path.parts)
```

Replace the final two lines of `get_object()` with:

```python
configurable_cls = self._configurable_classes[class_name]
canonical_path = self._canonical_config_path(path)
context = GPConfigurableContext(manager=self, path=canonical_path)
result = configurable_cls.from_config(config, context=context)

if not isinstance(result, configurable_cls):
    raise ConfigurableConstructionError(
        canonical_path,
        configurable_cls,
        type(result),
    )

return result
```

Update the `get_object()` docstring so its construction step names `from_config()`, and add `ConfigurableConstructionError` to `Raises:`. Do not add a `try` block around the hook.

- [ ] **Step 9: Run focused construction tests and lint**

Run:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_manager_objects.py tests/test_gpconfig_folder.py -v
.venv/Scripts/python.exe -m ruff check src/gpconfig/manager.py tests/test_manager_objects.py tests/test_gpconfig_folder.py
```

Expected: all manager-object and folder tests pass; Ruff reports no errors.

- [ ] **Step 10: Run all object-construction regression tests together**

Run:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_configurable.py tests/test_exceptions.py tests/test_exports.py tests/test_manager_objects.py tests/test_gpconfig_folder.py tests/test_integration.py tests/test_mock_configs.py -v
```

Expected: every listed test passes, including old single-argument subclasses and repeated `get_object()` calls returning distinct objects.

- [ ] **Step 11: Commit context-aware construction**

```powershell
git add -- src/gpconfig/manager.py tests/test_manager_objects.py tests/test_gpconfig_folder.py
git commit -m "feat: construct configurable objects with context"
```

---

### Task 4: Breaking-Change Migration Guide

**Files:**
- Create: `dev_docs/gpconfig-context-aware-object-construction-migration-guide.md`

**Interfaces:**
- Consumes: the final API names and error behavior implemented in Tasks 1-3.
- Produces: a standalone adaptation guide for users of duck-typed registrations or an existing incompatible `from_config()` method.

- [ ] **Step 1: Create the migration guide with concrete before-and-after examples**

Create `dev_docs/gpconfig-context-aware-object-construction-migration-guide.md` with this content:

````markdown
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
````

- [ ] **Step 2: Verify the guide is the only newly staged feature-facing document**

Run:

```powershell
git add -- dev_docs/gpconfig-context-aware-object-construction-migration-guide.md
git diff --cached --check
git diff --cached --name-only
```

Expected: the check exits successfully and the name list contains only `dev_docs/gpconfig-context-aware-object-construction-migration-guide.md`.

- [ ] **Step 3: Commit the migration guide**

```powershell
git commit -m "docs: add object construction migration guide"
```

---

### Task 5: Full Verification and Scope Audit

**Files:**
- Verify: all files changed by Tasks 1-4
- Verify unchanged: `README.md`, existing `docs/*.md`, existing `docs/zh/*.md`, `mkdocs.yml`, `src/gpconfig/__init__.py` version value

**Interfaces:**
- Consumes: all implementation, tests, exports, and migration guidance from Tasks 1-4.
- Produces: fresh evidence that the complete feature satisfies the design without unrelated changes.

- [ ] **Step 1: Run the complete test suite**

Run:

```powershell
.venv/Scripts/python.exe -m pytest
```

Expected: all tests pass with zero failures.

- [ ] **Step 2: Run the complete suite with coverage**

Run:

```powershell
.venv/Scripts/python.exe -m pytest --cov=gpconfig
```

Expected: all tests pass with zero failures and pytest-cov prints a coverage report for `gpconfig`.

- [ ] **Step 3: Run repository-wide lint**

Run:

```powershell
.venv/Scripts/python.exe -m ruff check .
```

Expected: `All checks passed!`.

- [ ] **Step 4: Check patch integrity and changed-file scope**

Run:

```powershell
git diff --check main...HEAD
git diff --name-only main...HEAD
git status --short --branch
```

Expected: no whitespace errors; changed files are limited to the approved design/plan files, the four source files, five test files, and the new migration guide; the branch is `context-aware-object-construction-refactor` with a clean worktree.

- [ ] **Step 5: Confirm the version and existing documentation remain untouched**

Run:

```powershell
git diff main...HEAD -- README.md docs/index.md docs/configurable.md docs/gpconfig.md docs/manager.md docs/exceptions.md docs/zh/index.md docs/zh/configurable.md docs/zh/gpconfig.md docs/zh/manager.md docs/zh/exceptions.md mkdocs.yml
Select-String -Path 'src/gpconfig/__init__.py' -Pattern '__version__ = "0.3.4"'
```

Expected: the documentation diff command has no output, and `Select-String` prints the unchanged `0.3.4` version line.

Do not create another commit in this task unless verification reveals a defect. If a defect is found, return to the task that owns it, add or strengthen a failing test, implement the minimal correction, rerun that task's focused verification, and commit the correction with the same Conventional Commit prefix as the owning task.
