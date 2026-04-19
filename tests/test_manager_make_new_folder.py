"""Tests for GPConfigManager.make_new_project_config_folder method."""

from pathlib import Path
from typing import ClassVar

import pytest

from gpconfig import GPConfig, GPConfigManager
from gpconfig.exceptions import ConfigFolderError, ConfigReadonlyError


class SimpleConfig(GPConfig):
    """Simple test config."""

    cfg_class_name: ClassVar[str] = "TestSimpleConfig"
    value: str = "default"


class NestedConfig(GPConfig):
    """Config with default_cfg_path."""

    cfg_class_name: ClassVar[str] = "TestNestedConfig"
    default_cfg_path: ClassVar[str] = "services"
    host: str = "localhost"
    port: int = 8080


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset class-level registries before each test."""
    GPConfigManager._config_classes = {}
    GPConfigManager._configurable_classes = {}
    yield
    GPConfigManager._config_classes = {}
    GPConfigManager._configurable_classes = {}


class TestMakeNewProjectConfigFolder:
    """Tests for make_new_project_config_folder method."""

    def test_creates_folder_with_configs_and_global_env(self, tmp_path: Path):
        """Should create folder with all configs and global_env.yaml."""
        # Arrange
        config = SimpleConfig()
        config.name = "test_config"

        folder_path = tmp_path / "myapp"

        # Act
        result = GPConfigManager.make_new_project_config_folder(
            project_name="myapp",
            cfgs=[config],
            global_env={"version": "1.0.0"},
            cfg_folder_path=str(folder_path),
        )

        # Assert
        assert result == folder_path
        assert folder_path.exists()
        assert (folder_path / "global_env.yaml").exists()
        assert (folder_path / "test_config.yaml").exists()

    def test_raises_error_when_folder_exists(self, tmp_path: Path):
        """Should raise ConfigFolderError if folder already exists."""
        # Arrange
        folder_path = tmp_path / "existing"
        folder_path.mkdir()
        (folder_path / "global_env.yaml").touch()

        config = SimpleConfig()
        config.name = "test"

        # Act & Assert
        with pytest.raises(ConfigFolderError) as exc_info:
            GPConfigManager.make_new_project_config_folder(
                project_name="existing", cfgs=[config], cfg_folder_path=str(folder_path)
            )
        assert "already exists" in str(exc_info.value)

    def test_raises_error_when_config_name_empty(self, tmp_path: Path):
        """Should raise ValueError if config.name is empty."""
        # Arrange
        config = SimpleConfig()
        # name is empty by default

        folder_path = tmp_path / "myapp"

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            GPConfigManager.make_new_project_config_folder(
                project_name="myapp", cfgs=[config], cfg_folder_path=str(folder_path)
            )
        assert "name" in str(exc_info.value).lower()

    def test_raises_error_when_config_readonly(self, tmp_path: Path):
        """Should raise ConfigReadonlyError if config.readonly is True."""
        # Arrange
        config = SimpleConfig(readonly=True)
        config.name = "test"

        folder_path = tmp_path / "myapp"

        # Act & Assert
        with pytest.raises(ConfigReadonlyError):
            GPConfigManager.make_new_project_config_folder(
                project_name="myapp", cfgs=[config], cfg_folder_path=str(folder_path)
            )

    def test_creates_subdirectories_from_default_cfg_path(self, tmp_path: Path):
        """Should create subdirectories based on default_cfg_path."""
        # Arrange
        config = NestedConfig()
        config.name = "api"

        folder_path = tmp_path / "myapp"

        # Act
        GPConfigManager.make_new_project_config_folder(
            project_name="myapp", cfgs=[config], cfg_folder_path=str(folder_path)
        )

        # Assert
        assert (folder_path / "services" / "api.yaml").exists()

    def test_uses_environment_variable_when_no_explicit_path(
        self, tmp_path: Path, monkeypatch
    ):
        """Should use env var path when cfg_folder_path not provided."""
        # Arrange
        env_path = tmp_path / "from_env"
        monkeypatch.setenv("MYAPP_CFG_PATH", str(env_path))

        config = SimpleConfig()
        config.name = "test"

        # Act
        result = GPConfigManager.make_new_project_config_folder(
            project_name="myapp", cfgs=[config]
        )

        # Assert
        assert result == env_path
        assert env_path.exists()

    def test_uses_home_directory_as_fallback(self, tmp_path: Path, monkeypatch):
        """Should use ~/{project_name}/ when no path or env var."""
        # Arrange - mock Path.home()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = SimpleConfig()
        config.name = "test"

        # Act
        result = GPConfigManager.make_new_project_config_folder(
            project_name="testproject", cfgs=[config]
        )

        # Assert
        expected_path = tmp_path / "testproject"
        assert result == expected_path
        assert expected_path.exists()

    def test_creates_empty_global_env_when_none(self, tmp_path: Path):
        """Should create empty global_env.yaml when global_env is None."""
        # Arrange
        config = SimpleConfig()
        config.name = "test"

        folder_path = tmp_path / "myapp"

        # Act
        GPConfigManager.make_new_project_config_folder(
            project_name="myapp",
            cfgs=[config],
            global_env=None,
            cfg_folder_path=str(folder_path),
        )

        # Assert
        global_env_file = folder_path / "global_env.yaml"
        assert global_env_file.exists()
        content = global_env_file.read_text()
        # Empty dict results in empty or "{}" content
        assert content.strip() in ("", "{}")
