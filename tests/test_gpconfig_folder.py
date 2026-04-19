"""Tests for GPConfigFolder class."""

import pytest
from pathlib import Path

from gpconfig.manager import GPConfigManager, GPConfigFolder
from gpconfig.config import GPConfig
from gpconfig.exceptions import ConfigNotFoundError


class TestConfig(GPConfig):
    """Test config class."""

    value: str = "default"


@pytest.fixture
def manager_with_folder(tmp_path: Path) -> GPConfigManager:
    """Create a manager with nested folder structure."""
    (tmp_path / "global_env.yaml").write_text("version: 1.0\n")

    # Create services folder with api.yaml inside
    services_folder = tmp_path / "services"
    services_folder.mkdir()
    (services_folder / "api.yaml").write_text("value: api_value\n")

    # Create nested folder
    nested_folder = services_folder / "nested"
    nested_folder.mkdir()
    (nested_folder / "config.yaml").write_text("value: nested_value\n")

    return GPConfigManager("testproject", cfg_folder=tmp_path)


class TestGPConfigFolder:
    """Test GPConfigFolder class."""

    def test_get_config_returns_folder_for_folder_path(self, manager_with_folder):
        """get_config returns GPConfigFolder when path is a folder."""
        result = manager_with_folder.get_config("services")
        assert isinstance(result, GPConfigFolder)
        assert result.path == "services"

    def test_get_config_returns_config_for_file_path(self, manager_with_folder):
        """get_config returns GPConfig when path is a file."""
        result = manager_with_folder.get_config("services.api", TestConfig)
        assert isinstance(result, TestConfig)
        assert result.value == "api_value"

    def test_folder_path_priority_when_no_config_cls(self, manager_with_folder):
        """When both file and folder exist, folder is returned if no config_cls."""
        # Create a file with same name as folder
        (manager_with_folder.cfg_folder / "services.yaml").write_text(
            "value: file_value\n"
        )

        result = manager_with_folder.get_config("services")
        assert isinstance(result, GPConfigFolder)

    def test_file_priority_when_config_cls_provided(self, manager_with_folder):
        """When both file and folder exist, file is returned if config_cls provided."""
        # Create a file with same name as folder
        (manager_with_folder.cfg_folder / "services.yaml").write_text(
            "value: file_value\n"
        )

        result = manager_with_folder.get_config("services", TestConfig)
        assert isinstance(result, TestConfig)
        assert result.value == "file_value"

    def test_folder_get_config(self, manager_with_folder):
        """GPConfigFolder.get_config delegates to manager with prefixed path."""
        folder = manager_with_folder.get_config("services")
        config = folder.get_config("api", TestConfig)
        assert isinstance(config, TestConfig)
        assert config.value == "api_value"

    def test_folder_get_config_nested(self, manager_with_folder):
        """GPConfigFolder.get_config works with nested paths."""
        folder = manager_with_folder.get_config("services")
        nested_folder = folder.get_config("nested")
        assert isinstance(nested_folder, GPConfigFolder)
        assert nested_folder.path == "services.nested"

    def test_folder_list_configs(self, manager_with_folder):
        """GPConfigFolder.list_configs returns items in folder."""
        folder = manager_with_folder.get_config("services")
        items = folder.list_configs()
        assert "api" in items
        assert "nested" in items

    def test_folder_get_object(self, manager_with_folder):
        """GPConfigFolder.get_object delegates to manager with prefixed path."""
        from gpconfig.configurable import GPConfigurable

        class TestService(GPConfigurable):
            pass

        # Register classes
        GPConfigManager.register_config_class(TestConfig)
        GPConfigManager.register_configurable_class(TestService)

        # Update config with configured_class_name
        (manager_with_folder.cfg_folder / "services" / "api.yaml").write_text(
            "value: api_value\nconfigured_class_name: TestService\n"
        )

        folder = manager_with_folder.get_config("services")
        obj = folder.get_object("api")
        assert isinstance(obj, TestService)

    def test_folder_is_cached(self, manager_with_folder):
        """GPConfigFolder instances are cached."""
        folder1 = manager_with_folder.get_config("services")
        folder2 = manager_with_folder.get_config("services")
        assert folder1 is folder2

    def test_folder_path_property(self, manager_with_folder):
        """GPConfigFolder.path returns the relative path."""
        folder = manager_with_folder.get_config("services.nested")
        assert folder.path == "services.nested"

    def test_get_config_raises_for_nonexistent_path(self, manager_with_folder):
        """get_config raises ConfigNotFoundError for nonexistent path."""
        with pytest.raises(ConfigNotFoundError):
            manager_with_folder.get_config("nonexistent")
