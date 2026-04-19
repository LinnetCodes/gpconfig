"""Tests for GPConfigManager.get_config method."""

import pytest
from pathlib import Path

from gpconfig.config import GPConfig
from gpconfig.manager import GPConfigManager
from gpconfig.exceptions import ConfigNotFoundError, ConfigValidationError


class DatabaseConfig(GPConfig):
    """Test config for database."""

    host: str
    port: int = 5432


class LLMConfig(GPConfig):
    """Test config for LLM providers."""

    api_key: str
    model: str
    temperature: float = 0.7


@pytest.fixture
def manager_with_configs(tmp_path: Path) -> GPConfigManager:
    """Create a manager with a populated config folder."""
    (tmp_path / "global_env.yaml").write_text("version: 1.0\ndebug: true\n")
    (tmp_path / "database.yaml").write_text("host: localhost\nport: 5432\n")

    llm_folder = tmp_path / "llm"
    llm_folder.mkdir()
    (llm_folder / "openai.yaml").write_text("api_key: sk-xxx\nmodel: gpt-4\n")

    return GPConfigManager("testproject", cfg_folder=tmp_path)


class TestGetConfig:
    """Test get_config method."""

    def test_get_config_returns_config_instance(self, manager_with_configs):
        """get_config returns a GPConfig instance."""
        config = manager_with_configs.get_config("database", DatabaseConfig)
        assert isinstance(config, DatabaseConfig)
        assert config.host == "localhost"
        assert config.port == 5432

    def test_get_config_sets_name_and_path(self, manager_with_configs):
        """get_config sets name and cfg_file_path on the config."""
        config = manager_with_configs.get_config("database", DatabaseConfig)
        assert config.name == "database"
        assert config.cfg_file_path.name == "database.yaml"

    def test_get_config_caches_config(self, manager_with_configs):
        """get_config caches loaded configs."""
        config1 = manager_with_configs.get_config("database", DatabaseConfig)
        config2 = manager_with_configs.get_config("database", DatabaseConfig)
        assert config1 is config2  # Same object from cache

    def test_get_config_nested_path(self, manager_with_configs):
        """get_config works with nested paths."""
        config = manager_with_configs.get_config("llm.openai", LLMConfig)
        assert config.api_key == "sk-xxx"
        assert config.model == "gpt-4"
        assert config.name == "openai"

    def test_get_config_returns_value_for_key_path(self, manager_with_configs):
        """get_config returns specific value when key is in path."""
        host = manager_with_configs.get_config("database.host")
        assert host == "localhost"

    def test_get_config_returns_nested_value(self, manager_with_configs):
        """get_config returns nested config value."""
        model = manager_with_configs.get_config("llm.openai.model")
        assert model == "gpt-4"

    def test_get_config_global_env_value(self, manager_with_configs):
        """get_config returns global_env value."""
        debug = manager_with_configs.get_config("global_env.debug")
        assert debug is True

    def test_get_config_raises_for_nonexistent_config(self, manager_with_configs):
        """get_config raises ConfigNotFoundError for nonexistent config."""
        with pytest.raises(ConfigNotFoundError) as exc_info:
            manager_with_configs.get_config("nonexistent", DatabaseConfig)
        assert exc_info.value.path == "nonexistent"

    def test_get_config_raises_for_nonexistent_key(self, manager_with_configs):
        """get_config raises ConfigNotFoundError for nonexistent key."""
        with pytest.raises(ConfigNotFoundError):
            manager_with_configs.get_config("database.nonexistent_key")

    def test_get_config_raises_validation_error_for_invalid_yaml(self, tmp_path):
        """get_config raises ConfigValidationError for invalid config."""
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        (tmp_path / "database.yaml").write_text("host: localhost\nport: not_a_number\n")

        manager = GPConfigManager("testproject", cfg_folder=tmp_path)

        with pytest.raises(ConfigValidationError) as exc_info:
            manager.get_config("database", DatabaseConfig)

        assert exc_info.value.path == "database"


class TestGetConfigFolderDetection:
    """Test folder detection in get_config."""

    def test_get_config_returns_folder_for_subfolder(self, manager_with_configs):
        """get_config returns GPConfigFolder for a subfolder path."""
        from gpconfig.manager import GPConfigFolder

        result = manager_with_configs.get_config("llm")
        assert isinstance(result, GPConfigFolder)
        assert result.path == "llm"

    def test_folder_from_manager_can_access_nested_config(self, manager_with_configs):
        """GPConfigFolder returned by manager can access nested configs."""
        folder = manager_with_configs.get_config("llm")
        config = folder.get_config("openai", LLMConfig)
        assert config.model == "gpt-4"
