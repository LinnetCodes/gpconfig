"""Tests using mock_configs folder for comprehensive config scenarios."""

import pytest
from pathlib import Path
from typing import ClassVar, Optional

from gpconfig import GPConfig, GPConfigurable, GPConfigManager, GPConfigFolder
from gpconfig.exceptions import ConfigNotFoundError, ConfigReadonlyError

# Path to mock configs folder
MOCK_CONFIGS_PATH = Path(__file__).parent / "mock_configs"


# ============================================================================
# Config Classes
# ============================================================================


class GlobalEnvConfig(GPConfig):
    """Global environment configuration."""

    cfg_class_name: ClassVar[str] = "GlobalEnvConfig"
    default_cfg_path: ClassVar[Optional[str]] = None  # Root level
    version: str
    app_name: str
    debug: bool
    log_level: str
    max_connections: int
    timeout_seconds: int


class AppConfig(GPConfig):
    """Application configuration (flat)."""

    cfg_class_name: ClassVar[str] = "AppConfig"
    default_cfg_path: ClassVar[Optional[str]] = ""  # Root level
    app_name: str
    host: str
    port: int
    workers: int
    enable_ssl: bool = False


class DatabaseConfig(GPConfig):
    """Database configuration (flat)."""

    cfg_class_name: ClassVar[str] = "DatabaseConfig"
    default_cfg_path: ClassVar[Optional[str]] = ""  # Root level
    host: str
    port: int
    username: str
    password: str
    database: str
    pool_size: int = 5
    ssl_mode: str = "prefer"


class ReadonlyConfig(GPConfig):
    """Readonly configuration for testing readonly flag."""

    cfg_class_name: ClassVar[str] = "ReadonlyConfig"
    default_cfg_path: ClassVar[Optional[str]] = ""  # Root level
    api_endpoint: str
    readonly: bool = False


class ApiConfig(GPConfig):
    """API configuration (3 levels deep)."""

    cfg_class_name: ClassVar[str] = "ApiConfig"
    default_cfg_path: ClassVar[Optional[str]] = "services/api"  # services/api folder
    version: str
    base_path: str
    rate_limit: int
    timeout_ms: int
    auth_required: bool = False
    graphql_enabled: bool = False


class WorkerConfig(GPConfig):
    """Worker configuration (2 levels deep)."""

    cfg_class_name: ClassVar[str] = "WorkerConfig"
    default_cfg_path: ClassVar[Optional[str]] = (
        "services/workers"  # services/workers folder
    )
    worker_type: str
    concurrency: int
    queue_name: str
    retry_attempts: int = 3


class DatabaseRoleConfig(GPConfig):
    """Database role configuration (2 levels deep)."""

    cfg_class_name: ClassVar[str] = "DatabaseRoleConfig"
    default_cfg_path: ClassVar[Optional[str]] = "databases"  # databases/{role} folder
    role: str
    host: str
    port: int
    database: str
    replication_enabled: bool = False
    read_only: bool = False


class CacheConfig(GPConfig):
    """Cache configuration (1 level deep)."""

    cfg_class_name: ClassVar[str] = "CacheConfig"
    default_cfg_path: ClassVar[Optional[str]] = "cache"  # cache folder
    provider: str
    host: str
    port: int
    ttl_seconds: int


# ============================================================================
# Configurable Classes
# ============================================================================


class Application(GPConfigurable):
    """Application configurable object."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config)
        self.app_name = config.app_name
        self.url = f"http://{config.host}:{config.port}"


class Database(GPConfigurable):
    """Database configurable object."""

    def __init__(self, config: DatabaseConfig) -> None:
        super().__init__(config)
        self.connection_string = (
            f"postgresql://{config.username}:{config.password}"
            f"@{config.host}:{config.port}/{config.database}"
        )


class ApiServer(GPConfigurable):
    """API server configurable object."""

    def __init__(self, config: ApiConfig) -> None:
        super().__init__(config)
        self.full_url = f"http://localhost:8000{config.base_path}"


class Worker(GPConfigurable):
    """Worker configurable object."""

    def __init__(self, config: WorkerConfig) -> None:
        super().__init__(config)
        self.identifier = f"{config.worker_type}-{config.queue_name}"


class CacheService(GPConfigurable):
    """Cache service configurable object."""

    def __init__(self, config: CacheConfig) -> None:
        super().__init__(config)
        self.connection_url = f"{config.provider}://{config.host}:{config.port}"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset class-level registries before each test."""
    GPConfigManager._config_classes = {}
    GPConfigManager._configurable_classes = {}
    yield
    GPConfigManager._config_classes = {}
    GPConfigManager._configurable_classes = {}


@pytest.fixture
def manager() -> GPConfigManager:
    """Create a GPConfigManager with mock_configs folder."""
    return GPConfigManager("testapp", cfg_folder=MOCK_CONFIGS_PATH)


# ============================================================================
# Tests: User Tests not generated by AI
# ============================================================================


class TestUserTests:
    """Test readonly configuration."""

    def test_mock_configs_user_tests(
        self, manager: GPConfigManager, tmp_path: Path
    ) -> None:
        """Readonly config raises error on save."""
        import shutil

        GPConfigManager.register_config_class(AppConfig)
        GPConfigManager.register_config_class(DatabaseConfig)
        GPConfigManager.register_config_class(ReadonlyConfig)
        GPConfigManager.register_config_class(ApiConfig)
        GPConfigManager.register_config_class(WorkerConfig)
        GPConfigManager.register_config_class(DatabaseRoleConfig)
        GPConfigManager.register_config_class(CacheConfig)
        GPConfigManager.register_config_class(ReadonlyConfig)

        GPConfigManager.register_configurable_class(Application)
        GPConfigManager.register_configurable_class(Database)
        GPConfigManager.register_configurable_class(ApiServer)
        GPConfigManager.register_configurable_class(Worker)
        GPConfigManager.register_configurable_class(CacheService)

        config = manager.get_config("database")
        assert isinstance(config, DatabaseConfig)

        config = manager.get_config("app")
        assert isinstance(config, AppConfig)

        config = manager.get_config("readonly_config")
        assert isinstance(config, ReadonlyConfig)

        assert manager.get_config("global_env.app_name") == "TestApp"

        assert isinstance(manager.get_config("cache.memcached"), CacheConfig)
        assert isinstance(manager.get_config("cache.redis"), CacheConfig)

        objs = manager.list_configs("cache")
        assert len(objs) == 2

        assert "memcached" in objs
        assert "redis" in objs

        objs = manager.list_configs("databases")
        assert len(objs) == 2
        assert "primary" in objs
        assert "replica" in objs

        objs = manager.list_configs("databases.primary")
        assert len(objs) == 1
        assert "postgres" in objs

        cfg = manager.get_config("databases.primary.postgres")
        assert isinstance(cfg, DatabaseRoleConfig)

        obj = manager.get_object("cache.redis")
        assert isinstance(obj, CacheService)

        folder = manager.get_config("databases")
        assert isinstance(folder, GPConfigFolder)
        for name in folder.list_configs():
            assert name in {"primary", "replica"}
        folder = folder.get_config("primary")
        assert isinstance(folder, GPConfigFolder)
        cfg = folder.get_config("postgres")
        assert isinstance(cfg, GPConfig)

        folder = manager.get_config("cache")
        assert isinstance(folder, GPConfigFolder)
        obj = folder.get_object("memcached")
        assert isinstance(obj, CacheService)

        cfgs = [
            manager.get_config("cache.memcached"),
            manager.get_config("cache.redis"),
            manager.get_config("app"),
            manager.get_config("database"),
        ]

        new_config_path = tmp_path / "test_app"
        GPConfigManager.make_new_project_config_folder(
            "test_app", cfgs, {"timeout": 10, "debug": True}, new_config_path
        )

        mgr = GPConfigManager("test_app", cfg_folder=new_config_path)

        assert mgr.project_name == "test_app"
        assert manager.project_name == "testapp"

        cfg_1 = manager.get_config("cache.memcached")
        cfg_2 = mgr.get_config("cache.memcached")
        assert cfg_1 == cfg_2

        cfg_1 = manager.get_config("app")
        cfg_2 = mgr.get_config("app")
        assert cfg_1 == cfg_2

        obj = mgr.get_object("cache.redis")
        assert isinstance(obj, CacheService)

        shutil.rmtree(new_config_path, ignore_errors=True)


# ============================================================================
# Tests: Global Environment
# ============================================================================


class TestGlobalEnv:
    """Test global_env.yaml loading."""

    def test_global_env_loaded(self, manager: GPConfigManager):
        """Global env is loaded during initialization."""
        assert manager.global_env["version"] == "1.0.0"
        assert manager.global_env["app_name"] == "TestApp"
        assert manager.global_env["debug"] is True
        assert manager.global_env["log_level"] == "DEBUG"
        assert manager.global_env["max_connections"] == 100

    def test_get_config_global_env_key(self, manager: GPConfigManager):
        """Can access global_env values via get_config."""
        assert manager.get_config("global_env.version") == "1.0.0"
        assert manager.get_config("global_env.debug") is True
        assert manager.get_config("global_env.timeout_seconds") == 30


# ============================================================================
# Tests: Flat Configs
# ============================================================================


class TestFlatConfigs:
    """Test flat configuration files (root level)."""

    def test_get_app_config(self, manager: GPConfigManager):
        """Can read app.yaml (flat config)."""
        config = manager.get_config("app", AppConfig)
        assert config.app_name == "my-application"
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.workers == 4
        assert config.enable_ssl is False

    def test_get_database_config(self, manager: GPConfigManager):
        """Can read database.yaml (flat config)."""
        config = manager.get_config("database", DatabaseConfig)
        assert config.host == "db.example.com"
        assert config.port == 5432
        assert config.username == "admin"
        assert config.database == "myapp_db"
        assert config.pool_size == 10

    def test_get_database_key_value(self, manager: GPConfigManager):
        """Can read specific key from flat config."""
        host = manager.get_config("database.host")
        assert host == "db.example.com"

        port = manager.get_config("database.port")
        assert port == 5432


# ============================================================================
# Tests: 1-Level Nested Configs
# ============================================================================


class TestOneLevelNested:
    """Test 1-level nested configs (cache/redis.yaml, cache/memcached.yaml)."""

    def test_get_redis_config(self, manager: GPConfigManager):
        """Can read cache/redis.yaml (1 level nested)."""
        config = manager.get_config("cache.redis", CacheConfig)
        assert config.provider == "redis"
        assert config.host == "cache.example.com"
        assert config.port == 6379
        assert config.ttl_seconds == 3600

    def test_get_memcached_config(self, manager: GPConfigManager):
        """Can read cache/memcached.yaml (1 level nested)."""
        config = manager.get_config("cache.memcached", CacheConfig)
        assert config.provider == "memcached"
        assert config.port == 11211

    def test_list_cache_folder(self, manager: GPConfigManager):
        """list_configs returns configs in cache folder."""
        items = manager.list_configs("cache")
        assert set(items) == {"redis", "memcached"}


# ============================================================================
# Tests: 2-Level Nested Configs
# ============================================================================


class TestTwoLevelNested:
    """Test 2-level nested configs (databases/primary/*, databases/replica/*, services/workers/*)."""

    def test_get_primary_database(self, manager: GPConfigManager):
        """Can read databases/primary/postgres.yaml (2 levels nested)."""
        config = manager.get_config("databases.primary.postgres", DatabaseRoleConfig)
        assert config.role == "primary"
        assert config.host == "primary.db.example.com"
        assert config.replication_enabled is True

    def test_get_replica_database(self, manager: GPConfigManager):
        """Can read databases/replica/postgres.yaml (2 levels nested)."""
        config = manager.get_config("databases.replica.postgres", DatabaseRoleConfig)
        assert config.role == "replica"
        assert config.host == "replica.db.example.com"
        assert config.read_only is True

    def test_get_email_worker(self, manager: GPConfigManager):
        """Can read services/workers/email.yaml (2 levels nested)."""
        config = manager.get_config("services.workers.email", WorkerConfig)
        assert config.worker_type == "email"
        assert config.concurrency == 5
        assert config.queue_name == "email_queue"

    def test_get_notification_worker(self, manager: GPConfigManager):
        """Can read services/workers/notification.yaml (2 levels nested)."""
        config = manager.get_config("services.workers.notification", WorkerConfig)
        assert config.worker_type == "notification"
        assert config.concurrency == 10

    def test_list_databases_primary(self, manager: GPConfigManager):
        """list_configs returns configs in databases/primary folder."""
        items = manager.list_configs("databases.primary")
        assert items == ["postgres"]

    def test_list_services_workers(self, manager: GPConfigManager):
        """list_configs returns configs in services/workers folder."""
        items = manager.list_configs("services.workers")
        assert set(items) == {"email", "notification"}


# ============================================================================
# Tests: 3-Level Nested Configs
# ============================================================================


class TestThreeLevelNested:
    """Test 3-level nested configs (services/api/v1/*, services/api/v2/*)."""

    def test_get_api_v1_config(self, manager: GPConfigManager):
        """Can read services/api/v1/config.yaml (3 levels nested)."""
        config = manager.get_config("services.api.v1.config", ApiConfig)
        assert config.version == "v1"
        assert config.base_path == "/api/v1"
        assert config.rate_limit == 100
        assert config.timeout_ms == 5000
        assert config.auth_required is True
        assert config.graphql_enabled is False

    def test_get_api_v2_config(self, manager: GPConfigManager):
        """Can read services/api/v2/config.yaml (3 levels nested)."""
        config = manager.get_config("services.api.v2.config", ApiConfig)
        assert config.version == "v2"
        assert config.base_path == "/api/v2"
        assert config.rate_limit == 200
        assert config.graphql_enabled is True

    def test_list_api_v1(self, manager: GPConfigManager):
        """list_configs returns configs in services/api/v1 folder."""
        items = manager.list_configs("services.api.v1")
        assert items == ["config"]

    def test_list_api_v2(self, manager: GPConfigManager):
        """list_configs returns configs in services/api/v2 folder."""
        items = manager.list_configs("services.api.v2")
        assert items == ["config"]


# ============================================================================
# Tests: Object Creation
# ============================================================================


class TestObjectCreation:
    """Test creating configurable objects from configs."""

    def test_create_application_object(self, manager: GPConfigManager):
        """Can create Application object from flat config."""
        GPConfigManager.register_config_class(AppConfig)
        GPConfigManager.register_configurable_class(Application)
        app = manager.get_object("app")
        assert isinstance(app, Application)
        assert app.app_name == "my-application"
        assert app.url == "http://0.0.0.0:8080"

    def test_create_database_object(self, manager: GPConfigManager):
        """Can create Database object from flat config."""
        GPConfigManager.register_config_class(DatabaseConfig)
        GPConfigManager.register_configurable_class(Database)
        db = manager.get_object("database")
        assert isinstance(db, Database)
        assert "db.example.com" in db.connection_string
        assert "admin" in db.connection_string

    def test_create_worker_object_from_config(self, manager: GPConfigManager):
        """Can create Worker object from 2-level nested config using get_config + manual instantiation."""
        config = manager.get_config("services.workers.email", WorkerConfig)
        worker = Worker(config)
        assert isinstance(worker, Worker)
        assert worker.identifier == "email-email_queue"

    def test_create_cache_object(self, manager: GPConfigManager):
        """Can create CacheService object from 1-level nested config."""
        GPConfigManager.register_config_class(CacheConfig)
        GPConfigManager.register_configurable_class(CacheService)
        cache = manager.get_object("cache.redis")
        assert isinstance(cache, CacheService)
        assert cache.connection_url == "redis://cache.example.com:6379"


# ============================================================================
# Tests: Listing
# ============================================================================


class TestListObjects:
    """Test list_configs across different folder depths."""

    def test_list_root(self, manager: GPConfigManager):
        """list_configs at root returns all top-level items."""
        items = manager.list_configs()
        # Should include flat configs and folders
        assert "app" in items
        assert "database" in items
        assert "cache" in items
        assert "services" in items
        assert "databases" in items
        # global_env should NOT be included
        assert "global_env" not in items

    def test_list_services_folder(self, manager: GPConfigManager):
        """list_configs returns subfolders at services level."""
        items = manager.list_configs("services")
        assert set(items) == {"api", "workers"}

    def test_list_api_folder(self, manager: GPConfigManager):
        """list_configs returns subfolders at services/api level."""
        items = manager.list_configs("services.api")
        assert set(items) == {"v1", "v2"}


# ============================================================================
# Tests: Error Cases
# ============================================================================


class TestErrorCases:
    """Test error handling."""

    def test_nonexistent_config_raises(self, manager: GPConfigManager):
        """Nonexistent config raises ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError):
            manager.get_config("nonexistent", AppConfig)

    def test_nonexistent_key_raises(self, manager: GPConfigManager):
        """Nonexistent key raises ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError):
            manager.get_config("database.nonexistent_key")

    def test_nonexistent_nested_path_raises(self, manager: GPConfigManager):
        """Nonexistent nested path raises ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError):
            manager.get_config("services.nonexistent.config", ApiConfig)

    def test_list_nonexistent_folder_raises(self, manager: GPConfigManager):
        """list_configs for nonexistent folder raises error."""
        with pytest.raises(ConfigNotFoundError):
            manager.list_configs("nonexistent_folder")


# ============================================================================
# Tests: Config Caching
# ============================================================================


class TestConfigCaching:
    """Test config caching behavior."""

    def test_config_is_cached(self, manager: GPConfigManager):
        """Same config instance is returned from cache."""
        config1 = manager.get_config("database", DatabaseConfig)
        config2 = manager.get_config("database", DatabaseConfig)
        assert config1 is config2

    def test_object_is_not_cached(self, manager: GPConfigManager):
        """get_object returns new instance each time."""
        GPConfigManager.register_config_class(AppConfig)
        GPConfigManager.register_configurable_class(Application)
        obj1 = manager.get_object("app")
        obj2 = manager.get_object("app")
        assert obj1 is not obj2


# ============================================================================
# Tests: Readonly Config
# ============================================================================


class TestReadonlyConfig:
    """Test readonly configuration."""

    def test_readonly_config_cannot_save(self, manager: GPConfigManager):
        """Readonly config raises error on save."""
        config = manager.get_config("readonly_config", ReadonlyConfig)
        # The readonly field is set in the YAML
        assert config.api_endpoint == "https://api.example.com"
        # Note: readonly is a field that can be set in YAML, but save() checks self.readonly
        # For this test, the YAML has readonly: true
        config.readonly = True
        config.cfg_file_path = MOCK_CONFIGS_PATH / "readonly_config.yaml"

        with pytest.raises(ConfigReadonlyError):
            config.save()


# ============================================================================
# Tests: Auto-detection from cfg_class_name
# ============================================================================


class TestAutoDetectConfigClass:
    """Test auto-detection of config class from cfg_class_name in YAML."""

    def test_get_config_auto_detects_class(self, manager: GPConfigManager):
        """get_config auto-detects class from cfg_class_name in YAML."""
        # Register the config class first
        GPConfigManager.register_config_class(DatabaseConfig)

        # Get config without specifying config_cls
        config = manager.get_config("database")

        # Should return DatabaseConfig instance, not dict
        assert isinstance(config, DatabaseConfig)
        assert config.host == "db.example.com"
        assert config.port == 5432

    def test_get_config_auto_detect_nested(self, manager: GPConfigManager):
        """get_config auto-detects class for nested config."""
        GPConfigManager.register_config_class(CacheConfig)

        config = manager.get_config("cache.redis")
        assert isinstance(config, CacheConfig)
        assert config.provider == "redis"

    def test_get_config_returns_dict_if_not_registered(self, manager: GPConfigManager):
        """get_config returns dict if cfg_class_name not found in registry."""
        # Don't register any class
        config = manager.get_config("database")
        # Should return raw dict
        assert isinstance(config, dict)
        assert config["host"] == "db.example.com"

    def test_get_config_explicit_class_overrides_auto_detect(
        self, manager: GPConfigManager
    ):
        """Explicit config_cls parameter overrides auto-detection."""
        GPConfigManager.register_config_class(DatabaseConfig)

        # Pass explicit class - should work even if auto-detect would fail
        config = manager.get_config("database", DatabaseConfig)
        assert isinstance(config, DatabaseConfig)


# ============================================================================
# Tests: Class-level Registration
# ============================================================================


class TestClassLevelRegistration:
    """Test class-level registration methods."""

    def test_register_config_class(self):
        """register_config_class registers class by name."""
        GPConfigManager.register_config_class(AppConfig)

        assert "AppConfig" in GPConfigManager._config_classes
        assert GPConfigManager._config_classes["AppConfig"] is AppConfig

    def test_register_config_class_duplicate(self):
        """register_config_class not raises error for duplicate registration."""
        GPConfigManager.register_config_class(AppConfig)
        GPConfigManager.register_config_class(AppConfig)

    def test_register_configurable_class(self):
        """register_configurable_class registers a configurable class."""
        GPConfigManager.register_configurable_class(Application)

        assert "Application" in GPConfigManager._configurable_classes
        assert GPConfigManager._configurable_classes["Application"] is Application

    def test_register_configurable_class_duplicate(self):
        """register_configurable_class not raises error for duplicate registration."""
        GPConfigManager.register_configurable_class(Application)
        GPConfigManager.register_configurable_class(Application)

    def test_get_object_uses_configured_class(self, manager: GPConfigManager):
        """get_object uses configured_class from config class."""
        GPConfigManager.register_config_class(AppConfig)
        GPConfigManager.register_configurable_class(Application)

        app = manager.get_object("app")
        assert isinstance(app, Application)
        assert app.app_name == "my-application"


# ============================================================================
# Tests: cfg_class_name in save()
# ============================================================================


class TestCfgClassNameSave:
    """Test that cfg_class_name is written when saving config."""

    def test_save_includes_cfg_class_name(self, manager: GPConfigManager, tmp_path):
        """save() includes cfg_class_name in the saved file."""
        import yaml

        GPConfigManager.register_config_class(DatabaseConfig)

        # Load config
        config = manager.get_config("database")

        # Save to a temp file
        temp_file = tmp_path / "test_save.yaml"
        config.cfg_file_path = temp_file
        config.readonly = False
        config.save()

        # Read the saved file and check cfg_class_name is present
        with open(temp_file, "r", encoding="utf-8") as f:
            saved_data = yaml.safe_load(f)

        assert "cfg_class_name" in saved_data
        assert saved_data["cfg_class_name"] == "DatabaseConfig"


# ============================================================================
# Tests: Manager save() method
# ============================================================================


class TestManagerSave:
    """Test GPConfigManager.save() method for new configs."""

    def test_save_new_config_to_root(self, tmp_path: Path):
        """Save a new config to root folder using default_cfg_path."""
        # Create a minimal config folder
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        manager = GPConfigManager("test", cfg_folder=tmp_path)

        # Create a new config with default_cfg_path = "" (root)
        new_config = AppConfig(app_name="new-app", host="0.0.0.0", port=9000, workers=2)
        new_config.name = "new_app"

        # Save using manager
        manager.save(new_config)

        # Verify file was created at root
        saved_file = tmp_path / "new_app.yaml"
        assert saved_file.exists()

        # Verify content
        config = manager.get_config("new_app", AppConfig)
        assert config.app_name == "new-app"
        assert config.port == 9000

    def test_save_new_config_to_nested_folder(self, tmp_path: Path):
        """Save a new config to nested folder using default_cfg_path."""
        # Create a minimal config folder
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        manager = GPConfigManager("test", cfg_folder=tmp_path)

        # Create a new config with default_cfg_path = "cache"
        new_config = CacheConfig(
            provider="custom", host="custom.host", port=9999, ttl_seconds=600
        )
        new_config.name = "custom_cache"

        # Save using manager
        manager.save(new_config)

        # Verify file was created in cache folder
        saved_file = tmp_path / "cache" / "custom_cache.yaml"
        assert saved_file.exists()

        # Verify content
        GPConfigManager.register_config_class(CacheConfig)
        config = manager.get_config("cache.custom_cache")
        assert config.provider == "custom"
        assert config.port == 9999

    def test_save_with_explicit_path(self, tmp_path: Path):
        """Save a new config with explicit relative path."""
        # Create a minimal config folder
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        manager = GPConfigManager("test", cfg_folder=tmp_path)

        # Create a new config
        new_config = AppConfig(
            app_name="explicit-app", host="1.2.3.4", port=8080, workers=1
        )
        new_config.name = "explicit_app"

        # Save with explicit path (nested folder)
        manager.save(new_config, path="custom/folder/explicit_app")

        # Verify file was created at explicit path
        saved_file = tmp_path / "custom" / "folder" / "explicit_app.yaml"
        assert saved_file.exists()

    def test_save_with_explicit_path_dot_notation(self, tmp_path: Path):
        """Save a new config with explicit path using dot notation."""
        # Create a minimal config folder
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        manager = GPConfigManager("test", cfg_folder=tmp_path)

        # Create a new config
        new_config = DatabaseConfig(
            host="db.custom.com",
            port=5433,
            username="user",
            password="pass",
            database="custom_db",
        )
        new_config.name = "custom_db"

        # Save with explicit path using dot notation
        manager.save(new_config, path="databases.replica.custom_db")

        # Verify file was created
        saved_file = tmp_path / "databases" / "replica" / "custom_db.yaml"
        assert saved_file.exists()

    def test_save_raises_error_for_readonly_config(self, tmp_path: Path):
        """Save raises error for readonly config."""
        # Create a minimal config folder
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        manager = GPConfigManager("test", cfg_folder=tmp_path)

        # Create a readonly config
        new_config = AppConfig(
            app_name="readonly-app", host="0.0.0.0", port=8080, workers=1
        )
        new_config.name = "readonly_app"
        new_config.readonly = True

        with pytest.raises(ConfigReadonlyError):
            manager.save(new_config)

    def test_save_raises_error_for_empty_name(self, tmp_path: Path):
        """Save raises error for config with empty name."""
        # Create a minimal config folder
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        manager = GPConfigManager("test", cfg_folder=tmp_path)

        # Create a config without name
        new_config = AppConfig(
            app_name="no-name-app", host="0.0.0.0", port=8080, workers=1
        )

        with pytest.raises(ValueError, match="name"):
            manager.save(new_config)

    def test_save_updates_cache(self, tmp_path: Path):
        """Save updates the config cache."""
        # Create a minimal config folder
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        manager = GPConfigManager("test", cfg_folder=tmp_path)

        # Create and save a config
        new_config = AppConfig(
            app_name="cached-app", host="0.0.0.0", port=8080, workers=1
        )
        new_config.name = "cached_app"
        manager.save(new_config)

        # Get from cache should return the same instance
        cached_config = manager.get_config("cached_app", AppConfig)
        assert cached_config.app_name == "cached-app"
        assert cached_config is new_config  # Same instance from cache

    def test_save_non_gpconfig_raises_type_error(self, tmp_path: Path):
        """Save raises TypeError for non-GPConfig objects."""
        # Create a minimal config folder
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        manager = GPConfigManager("test", cfg_folder=tmp_path)

        with pytest.raises(TypeError):
            manager.save("not a config")  # type: ignore
