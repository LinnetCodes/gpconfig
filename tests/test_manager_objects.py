"""Tests for GPConfigManager object registration and creation."""

import pytest
from pathlib import Path
from typing import ClassVar

from gpconfig.config import GPConfig
from gpconfig.configurable import GPConfigurable
from gpconfig.manager import GPConfigManager
from gpconfig.exceptions import RegistrationError, ConfigNotFoundError


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
    """Reset class-level registries before each test."""
    GPConfigManager._config_classes = {}
    GPConfigManager._configurable_classes = {}
    yield
    GPConfigManager._config_classes = {}
    GPConfigManager._configurable_classes = {}


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


class TestConfigurableRegistryRemoved:
    """Test that _configurable_registry is removed."""

    def test_configurable_registry_does_not_exist(self):
        """_configurable_registry should be removed."""
        assert not hasattr(GPConfigManager, "_configurable_registry")


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
