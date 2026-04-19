"""Integration tests for gpconfig library."""

import pytest
from pathlib import Path
from typing import ClassVar

from gpconfig import (
    GPConfig,
    GPConfigurable,
    GPConfigManager,
)


class DatabaseConfig(GPConfig):
    """Database configuration."""

    cfg_class_name: ClassVar[str] = "IntegrationDatabaseConfig"
    host: str
    port: int = 5432
    username: str
    password: str
    database: str


class Database(GPConfigurable):
    """Database connection object."""

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        self.database = config.database

    @property
    def connection_string(self) -> str:
        return (
            f"postgresql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class LLMConfig(GPConfig):
    """LLM provider configuration."""

    cfg_class_name: ClassVar[str] = "IntegrationLLMConfig"
    api_key: str
    model: str
    temperature: float = 0.7


class LLMProvider(GPConfigurable):
    """LLM provider object."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self.api_key = config.api_key
        self.model = config.model
        self.temperature = config.temperature


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset class-level registries before each test."""
    GPConfigManager._config_classes = {}
    GPConfigManager._configurable_classes = {}
    yield
    GPConfigManager._config_classes = {}
    GPConfigManager._configurable_classes = {}


class TestFullWorkflow:
    """Test complete workflow from config files to objects."""

    @pytest.fixture
    def config_folder(self, tmp_path: Path) -> Path:
        """Create a complete config folder structure."""
        # Global env
        (tmp_path / "global_env.yaml").write_text("""
version: "1.0.0"
debug: true
log_level: INFO
""")

        # Flat config - database
        (tmp_path / "database.yaml").write_text("""
cfg_class_name: "IntegrationDatabaseConfig"
configured_class_name: "Database"
host: db.example.com
port: 5432
username: admin
password: secret123
database: myapp
""")

        # Nested configs - LLM providers
        llm_folder = tmp_path / "llm"
        llm_folder.mkdir()

        (llm_folder / "openai.yaml").write_text("""
cfg_class_name: "IntegrationLLMConfig"
configured_class_name: "LLMProvider"
api_key: sk-openai-key
model: gpt-4
temperature: 0.8
""")

        (llm_folder / "anthropic.yaml").write_text("""
cfg_class_name: "IntegrationLLMConfig"
configured_class_name: "LLMProvider"
api_key: sk-anthropic-key
model: claude-3-opus
temperature: 0.5
""")

        return tmp_path

    def test_full_workflow(self, config_folder):
        """Test complete workflow: init manager, register, get configs and objects."""
        # Initialize manager
        manager = GPConfigManager("myapp", cfg_folder=config_folder)

        # Verify global env loaded
        assert manager.global_env["version"] == "1.0.0"
        assert manager.global_env["debug"] is True
        assert manager.global_env["log_level"] == "INFO"

        # Register config classes (class-level)
        GPConfigManager.register_config_class(DatabaseConfig)
        GPConfigManager.register_config_class(LLMConfig)

        # Register configurable classes (class-level)
        GPConfigManager.register_configurable_class(Database)
        GPConfigManager.register_configurable_class(LLMProvider)

        # Get global env values
        version = manager.get_config("global_env.version")
        assert version == "1.0.0"

        debug = manager.get_config("global_env.debug")
        assert debug is True

        # Get database config
        db_config = manager.get_config("database", DatabaseConfig)
        assert db_config.host == "db.example.com"
        assert db_config.port == 5432
        assert db_config.name == "database"

        # Get specific database config value
        host = manager.get_config("database.host")
        assert host == "db.example.com"

        # Create database object
        db = manager.get_object("database")
        assert isinstance(db, Database)
        assert db.connection_string == (
            "postgresql://admin:secret123@db.example.com:5432/myapp"
        )

        # List root configs
        root_items = manager.list_configs()
        assert "database" in root_items
        assert "llm" in root_items

        # List LLM configs
        llm_items = manager.list_configs("llm")
        assert set(llm_items) == {"openai", "anthropic"}

        # Get nested config
        openai_config = manager.get_config("llm.openai", LLMConfig)
        assert openai_config.api_key == "sk-openai-key"
        assert openai_config.model == "gpt-4"
        assert openai_config.temperature == 0.8

        # Create LLM object
        llm = manager.get_object("llm.openai")
        assert isinstance(llm, LLMProvider)
        assert llm.model == "gpt-4"

        # Get nested config value
        model = manager.get_config("llm.anthropic.model")
        assert model == "claude-3-opus"

        # Verify new instance each time
        db1 = manager.get_object("database")
        db2 = manager.get_object("database")
        assert db1 is not db2

    def test_config_save_workflow(self, config_folder):
        """Test config modification and save."""
        manager = GPConfigManager("myapp", cfg_folder=config_folder)

        # Get config
        db_config = manager.get_config("database", DatabaseConfig)

        # Modify config
        db_config.port = 5433

        # Save config
        db_config.save()

        # Verify file was updated
        yaml_content = (config_folder / "database.yaml").read_text()
        assert "5433" in yaml_content

        # Clear cache and reload to verify persistence
        manager._config_cache.clear()
        reloaded = manager.get_config("database", DatabaseConfig)
        assert reloaded.port == 5433
