"""Tests for GPConfigManager path parsing."""

import pytest
from pathlib import Path

from gpconfig.manager import GPConfigManager
from gpconfig.exceptions import ConfigNotFoundError


@pytest.fixture
def manager_with_configs(tmp_path: Path) -> GPConfigManager:
    """Create a manager with a populated config folder."""
    # Create global_env.yaml
    (tmp_path / "global_env.yaml").write_text("version: 1.0\ndebug: true\n")

    # Create flat configs
    (tmp_path / "database.yaml").write_text("host: localhost\nport: 5432\n")

    # Create nested configs
    llm_folder = tmp_path / "llm"
    llm_folder.mkdir()
    (llm_folder / "openai.yaml").write_text("api_key: sk-xxx\nmodel: gpt-4\n")
    (llm_folder / "anthropic.yaml").write_text("api_key: sk-yyy\nmodel: claude-3\n")

    return GPConfigManager("testproject", cfg_folder=tmp_path)


class TestPathParsing:
    """Test internal path parsing logic."""

    def test_parse_flat_config_path(self, manager_with_configs: GPConfigManager):
        """Parse path to flat config file."""
        file_path, key = manager_with_configs._parse_path("database")
        assert file_path.name == "database.yaml"
        assert key is None

    def test_parse_flat_config_with_key(self, manager_with_configs: GPConfigManager):
        """Parse path to flat config with key."""
        file_path, key = manager_with_configs._parse_path("database.host")
        assert file_path.name == "database.yaml"
        assert key == "host"

    def test_parse_nested_config_path(self, manager_with_configs: GPConfigManager):
        """Parse path to nested config file."""
        file_path, key = manager_with_configs._parse_path("llm.openai")
        assert file_path.parent.name == "llm"
        assert file_path.name == "openai.yaml"
        assert key is None

    def test_parse_nested_config_with_key(self, manager_with_configs: GPConfigManager):
        """Parse path to nested config with key."""
        file_path, key = manager_with_configs._parse_path("llm.openai.model")
        assert file_path.parent.name == "llm"
        assert file_path.name == "openai.yaml"
        assert key == "model"

    def test_parse_global_env_path(self, manager_with_configs: GPConfigManager):
        """Parse path to global_env."""
        file_path, key = manager_with_configs._parse_path("global_env.debug")
        assert file_path.name == "global_env.yaml"
        assert key == "debug"

    def test_parse_path_with_project_prefix(
        self, manager_with_configs: GPConfigManager
    ):
        """Parse path with project name prefix."""
        file_path, key = manager_with_configs._parse_path("testproject.database")
        assert file_path.name == "database.yaml"
        assert key is None

    def test_parse_nonexistent_path_raises(self, manager_with_configs: GPConfigManager):
        """Parse nonexistent path raises ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError) as exc_info:
            manager_with_configs._parse_path("nonexistent")

        assert exc_info.value.path == "nonexistent"

    def test_parse_global_env_without_key_raises(
        self, manager_with_configs: GPConfigManager
    ):
        """Parse global_env without key raises error."""
        with pytest.raises(ConfigNotFoundError):
            manager_with_configs._parse_path("global_env")
