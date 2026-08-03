"""Tests for GPConfigManager object registration and creation."""

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


class DatabaseConfig(GPConfig):
    """Test config for database."""

    cfg_class_name: ClassVar[str] = "TestObjectsDatabaseConfig"
    host: str
    port: int = 5432


class Database(GPConfigurable):
    """Test configurable for database."""

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.connection_string = f"postgresql://{config.host}:{config.port}"


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


class CacheConfig(GPConfig):
    """Test config for cache."""

    cfg_class_name: ClassVar[str] = "TestObjectsCacheConfig"
    host: str
    ttl: int = 3600


class Cache(GPConfigurable):
    """Test configurable for cache."""

    def __init__(self, config: CacheConfig) -> None:
        super().__init__(config)
        self.ttl = config.ttl


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset class-level registries and construction observations."""
    GPConfigManager.reset_registries()
    ContextAwareDatabase.received_contexts.clear()
    yield
    GPConfigManager.reset_registries()
    ContextAwareDatabase.received_contexts.clear()


@pytest.fixture
def manager_with_configs(tmp_path: Path) -> GPConfigManager:
    """Create a manager with a populated config folder."""
    (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
    (tmp_path / "database.yaml").write_text(
        "cfg_class_name: 'TestObjectsDatabaseConfig'\n"
        "configured_class_name: 'Database'\n"
        "host: localhost\n"
        "port: 5432\n"
    )

    return GPConfigManager("testproject", cfg_folder=tmp_path)


class TestGetObject:
    """Test get_object method."""

    def test_get_object_creates_instance(self, manager_with_configs):
        """get_object creates a configurable instance."""
        GPConfigManager.register_config_class(DatabaseConfig)
        GPConfigManager.register_configurable_class(Database)
        db = manager_with_configs.get_object("database")

        assert isinstance(db, Database)
        assert db.connection_string == "postgresql://localhost:5432"

    def test_get_object_returns_new_instance_each_time(self, manager_with_configs):
        """get_object returns a new instance on each call (no caching)."""
        GPConfigManager.register_config_class(DatabaseConfig)
        GPConfigManager.register_configurable_class(Database)
        db1 = manager_with_configs.get_object("database")
        db2 = manager_with_configs.get_object("database")

        assert db1 is not db2
        assert db1.connection_string == db2.connection_string

    def test_get_object_unregistered_config_raises(self, manager_with_configs):
        """get_object raises error for unregistered config class."""
        # Don't register DatabaseConfig
        with pytest.raises(RegistrationError) as exc_info:
            manager_with_configs.get_object("database")

        # Error can be about either config class or configured class not being registered
        error_msg = str(exc_info.value).lower()
        assert (
            "no registered config class" in error_msg or "not registered" in error_msg
        )

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


class TestListObjects:
    """Test list_configs method."""

    @pytest.fixture
    def manager_with_nested_configs(self, tmp_path: Path):
        """Create manager with nested config structure."""
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        (tmp_path / "database.yaml").write_text("host: localhost\n")

        services = tmp_path / "services"
        services.mkdir()
        (services / "api.yaml").write_text("port: 8000\n")
        (services / "worker.yaml").write_text("workers: 4\n")

        llm = tmp_path / "llm"
        llm.mkdir()
        (llm / "openai.yaml").write_text("model: gpt-4\n")
        (llm / "anthropic.yaml").write_text("model: claude-3\n")

        return GPConfigManager("testproject", cfg_folder=tmp_path)

    def test_list_configs_root(self, manager_with_nested_configs):
        """list_configs returns all top-level configs and folders."""
        items = manager_with_nested_configs.list_configs()
        assert "database" in items
        assert "services" in items
        assert "llm" in items
        assert "global_env" not in items  # global_env is excluded

    def test_list_configs_folder(self, manager_with_nested_configs):
        """list_configs returns configs in a specific folder."""
        items = manager_with_nested_configs.list_configs("llm")
        assert set(items) == {"openai", "anthropic"}

    def test_list_configs_nested_folder(self, manager_with_nested_configs):
        """list_configs works with nested folder paths."""
        items = manager_with_nested_configs.list_configs("services")
        assert set(items) == {"api", "worker"}

    def test_list_configs_nonexistent_folder_raises(self, manager_with_nested_configs):
        """list_configs raises error for nonexistent folder."""
        with pytest.raises(ConfigNotFoundError):
            manager_with_nested_configs.list_configs("nonexistent")


class TestConfigurableClassesRegistry:
    """Test _configurable_classes class variable."""

    def test_configurable_classes_exists(self):
        """_configurable_classes class variable exists."""
        # Check it's defined in the class's own __dict__, not just accessible
        assert "_configurable_classes" in GPConfigManager.__dict__

    def test_configurable_classes_is_dict(self):
        """_configurable_classes is a dict."""
        assert isinstance(GPConfigManager._configurable_classes, dict)


class TestRegisterConfigurableClassSingleParam:
    """Test register_configurable_class with single parameter."""

    def test_register_single_param_registers_by_name(self):
        """register_configurable_class registers by class __name__."""
        GPConfigManager.register_configurable_class(Database)
        assert "Database" in GPConfigManager._configurable_classes
        assert GPConfigManager._configurable_classes["Database"] is Database

    def test_register_idempotent_same_class(self):
        """Re-registering the same class is idempotent (no error)."""
        GPConfigManager.register_configurable_class(Database)
        GPConfigManager.register_configurable_class(Database)  # Should not raise
        assert GPConfigManager._configurable_classes["Database"] is Database

    def test_register_different_class_same_name_raises(self):
        """Registering a different class with same name raises error."""
        # Create a conflict by manually inserting into registry first
        GPConfigManager._configurable_classes["ConflictClass"] = Database

        class ConflictClass(Cache):
            pass

        with pytest.raises(RegistrationError) as exc_info:
            GPConfigManager.register_configurable_class(ConflictClass)

        assert "already registered" in str(exc_info.value).lower()

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


class TestConfigurableRegistryRemoved:
    """Test that _configurable_registry is removed."""

    def test_configurable_registry_does_not_exist(self):
        """_configurable_registry should be removed."""
        assert not hasattr(GPConfigManager, "_configurable_registry")


class TestResetRegistries:
    """Test GPConfigManager.reset_registries() classmethod."""

    def test_reset_clears_both_registries_after_registration(self):
        """reset_registries() empties both _config_classes and _configurable_classes."""
        GPConfigManager.register_config_class(DatabaseConfig)
        GPConfigManager.register_configurable_class(Database)

        # Sanity: registries are populated before reset
        assert len(GPConfigManager._config_classes) > 0
        assert len(GPConfigManager._configurable_classes) > 0

        GPConfigManager.reset_registries()

        assert GPConfigManager._config_classes == {}
        assert GPConfigManager._configurable_classes == {}

    def test_reset_when_already_empty_is_noop(self):
        """reset_registries() does not error when registries are already empty."""
        GPConfigManager.reset_registries()  # registries already cleared by autouse fixture
        assert GPConfigManager._config_classes == {}
        assert GPConfigManager._configurable_classes == {}

        # Calling again must still be safe
        GPConfigManager.reset_registries()
        assert GPConfigManager._config_classes == {}
        assert GPConfigManager._configurable_classes == {}

    def test_reset_preserves_dict_object_identity(self):
        """reset_registries() uses .clear(), so the dict objects keep their identity."""
        config_classes_before = GPConfigManager._config_classes
        configurable_classes_before = GPConfigManager._configurable_classes

        GPConfigManager.register_config_class(DatabaseConfig)
        GPConfigManager.register_configurable_class(Database)

        GPConfigManager.reset_registries()

        # Same dict objects (mutated in place), not reassigned to new dicts
        assert GPConfigManager._config_classes is config_classes_before
        assert GPConfigManager._configurable_classes is configurable_classes_before


class TestGetObjectWithConfiguredClassName:
    """Test get_object using configured_class_name from config."""

    @pytest.fixture
    def manager_with_configured_name(self, tmp_path: Path):
        """Create manager with config containing configured_class_name."""
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        (tmp_path / "database.yaml").write_text(
            "cfg_class_name: 'TestObjectsDatabaseConfig'\n"
            "configured_class_name: 'Database'\n"
            "host: localhost\n"
            "port: 5432\n"
        )
        return GPConfigManager("testproject", cfg_folder=tmp_path)

    def test_get_object_uses_configured_class_name(self, manager_with_configured_name):
        """get_object reads configured_class_name from config."""
        GPConfigManager.register_config_class(DatabaseConfig)
        GPConfigManager.register_configurable_class(Database)

        db = manager_with_configured_name.get_object("database")
        assert isinstance(db, Database)
        assert db.connection_string == "postgresql://localhost:5432"

    def test_get_object_raises_when_configured_class_name_missing(
        self, manager_with_configured_name
    ):
        """get_object raises error when configured_class_name is not in config."""
        GPConfigManager.register_config_class(DatabaseConfig)
        # Don't register configurable class

        # Create a config without configured_class_name
        (manager_with_configured_name.cfg_folder / "database.yaml").write_text(
            "cfg_class_name: 'TestObjectsDatabaseConfig'\nhost: localhost\nport: 5432\n"
        )

        with pytest.raises(RegistrationError) as exc_info:
            manager_with_configured_name.get_object("database")

        assert "configured_class_name" in str(exc_info.value).lower()

    def test_get_object_raises_when_class_not_registered(
        self, manager_with_configured_name
    ):
        """get_object raises error when configured_class_name not in registry."""
        GPConfigManager.register_config_class(DatabaseConfig)
        # Don't register Database

        with pytest.raises(RegistrationError) as exc_info:
            manager_with_configured_name.get_object("database")

        assert "not registered" in str(exc_info.value).lower()
