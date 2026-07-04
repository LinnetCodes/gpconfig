"""Tests for GPConfig base class."""

import pytest
from pathlib import Path
from typing import ClassVar
from pydantic import ValidationError
from gpconfig.config import GPConfig


class SimpleConfig(GPConfig):
    """Simple test config with required and optional fields."""

    cfg_class_name: ClassVar[str] = "SimpleConfig"
    host: str
    port: int = 8080


class TestGPConfigBasics:
    """Test basic GPConfig functionality."""

    def test_inherits_from_pydantic_settings(self):
        """GPConfig should work with pydantic validation."""
        config = SimpleConfig(host="localhost")
        assert config.host == "localhost"
        assert config.port == 8080

    def test_default_values(self):
        """Test that default values are applied."""
        config = SimpleConfig(host="localhost")
        assert config.name == ""
        assert config.cfg_file_path == Path()
        assert config.readonly is False

    def test_can_set_name_and_path(self):
        """name and cfg_file_path can be set after creation."""
        config = SimpleConfig(host="localhost")
        config.name = "test_config"
        config.cfg_file_path = Path("/some/path.yaml")
        assert config.name == "test_config"
        assert config.cfg_file_path == Path("/some/path.yaml")

    def test_readonly_can_be_set(self):
        """readonly can be set to True."""
        config = SimpleConfig(host="localhost", readonly=True)
        assert config.readonly is True

    def test_extra_fields_forbidden(self):
        """Unknown fields should raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            SimpleConfig(host="localhost", unknown_field="value")
        assert "extra" in str(exc_info.value).lower()


class TestGPConfigClassVars:
    """Test class-level variables."""

    def test_default_cfg_path_defaults_to_none(self):
        assert GPConfig.default_cfg_path is None

    def test_subclass_can_override_class_vars(self):
        class CustomConfig(GPConfig):
            default_cfg_path = "custom/default"  # legal folder-only path
            value: str

        assert CustomConfig.default_cfg_path == "custom/default"


class TestDefaultCfgPathValidation:
    """GPConfig.__init_subclass__ validates default_cfg_path at class-definition time.

    This is the fail-early counterpart to the runtime check in
    GPConfigManager._resolve_save_folder. The class-definition check catches
    typos (e.g. 'cache/redis.yaml', 'llm.openai') at import time rather than on
    the first save() call.
    """

    # ------------------------------------------------------------------
    # Valid values — must NOT raise at class definition
    # ------------------------------------------------------------------

    def test_explicit_none_allowed(self):
        """default_cfg_path = None (explicit) — OK."""

        class NoneConfig(GPConfig):
            default_cfg_path = None
            value: str = ""

        assert NoneConfig.default_cfg_path is None

    def test_single_segment_allowed(self):
        """default_cfg_path = 'cache' (single segment) — OK."""

        class CacheConfig(GPConfig):
            default_cfg_path = "cache"
            value: str = ""

        assert CacheConfig.default_cfg_path == "cache"

    def test_slash_separated_allowed(self):
        """default_cfg_path = 'cache/redis' (file_path style) — OK."""

        class SlashConfig(GPConfig):
            default_cfg_path = "cache/redis"
            value: str = ""

        assert SlashConfig.default_cfg_path == "cache/redis"

    def test_backslash_separated_allowed(self):
        """default_cfg_path = 'cache\\\\redis' (backslash) — OK.

        The class-def check only rejects '.'; runtime normalises backslashes.
        """

        class BackslashConfig(GPConfig):
            default_cfg_path = "cache\\redis"
            value: str = ""

        assert BackslashConfig.default_cfg_path == "cache\\redis"

    def test_not_overriding_inherits_none(self):
        """A subclass that does NOT override default_cfg_path inherits None.

        No validation should be triggered for the inherited default.
        """

        class InheritsConfig(GPConfig):
            value: str = ""

        assert InheritsConfig.default_cfg_path is None

    def test_empty_string_allowed(self):
        """default_cfg_path = '' (empty string) — OK.

        Empty string is allowed at runtime (_resolve_save_folder treats it as
        cfg_folder root) and contains no '.', so class-def must also allow it.
        """

        class EmptyConfig(GPConfig):
            default_cfg_path = ""
            value: str = ""

        assert EmptyConfig.default_cfg_path == ""

    # ------------------------------------------------------------------
    # Invalid values — must raise at class definition
    # ------------------------------------------------------------------

    def test_cfg_path_style_rejected(self):
        """default_cfg_path = 'llm.openai' -> ValueError (cfg_path style)."""
        with pytest.raises(ValueError, match=r"must not contain '\.'"):

            class BadConfig(GPConfig):
                default_cfg_path = "llm.openai"

    def test_yaml_suffix_rejected(self):
        """default_cfg_path = 'cache/redis.yaml' -> ValueError (.yaml suffix)."""
        with pytest.raises(ValueError, match=r"must not contain '\.'"):

            class BadConfig(GPConfig):
                default_cfg_path = "cache/redis.yaml"

    def test_dotdot_traversal_rejected(self):
        """default_cfg_path = '../escape' -> ValueError (.. traversal)."""
        with pytest.raises(ValueError, match=r"must not contain '\.'"):

            class BadConfig(GPConfig):
                default_cfg_path = "../escape"

    def test_leading_dot_rejected(self):
        """default_cfg_path = '.hidden' -> ValueError (leading dot)."""
        with pytest.raises(ValueError, match=r"must not contain '\.'"):

            class BadConfig(GPConfig):
                default_cfg_path = ".hidden"

    def test_non_string_rejected(self):
        """default_cfg_path = 123 (non-string, non-None) -> TypeError."""
        with pytest.raises(TypeError, match="must be a string or None"):

            class BadConfig(GPConfig):
                default_cfg_path = 123  # type: ignore[assignment]

    def test_error_message_mentions_class_name(self):
        """The ValueError message names the offending subclass."""
        with pytest.raises(ValueError, match="BadNamedConfig"):

            class BadNamedConfig(GPConfig):
                default_cfg_path = "llm.openai"


class TestGPConfigSave:
    """Test GPConfig.save() method."""

    def test_save_raises_readonly_error_when_readonly(self, tmp_path: Path):
        """Saving a readonly config should raise ConfigReadonlyError."""
        from gpconfig.exceptions import ConfigReadonlyError

        config = SimpleConfig(host="localhost", readonly=True)
        config.name = "test"
        config.cfg_file_path = tmp_path / "test.yaml"

        with pytest.raises(ConfigReadonlyError):
            config.save()

    def test_save_writes_yaml_file(self, tmp_path: Path):
        """Save should write config to YAML file."""
        config = SimpleConfig(host="localhost", port=9000)
        config.name = "test"
        config.cfg_file_path = tmp_path / "test.yaml"
        config.save()

        assert config.cfg_file_path.exists()
        content = config.cfg_file_path.read_text()
        assert "host: localhost" in content
        assert "port: 9000" in content

    def test_save_excludes_non_yaml_fields(self, tmp_path: Path):
        """Save should exclude name, cfg_file_path, readonly from YAML, but include cfg_class_name."""
        config = SimpleConfig(host="localhost", readonly=True)
        config.name = "test_config"
        config.cfg_file_path = tmp_path / "test.yaml"
        # Temporarily set readonly to False to allow save
        config.readonly = False
        config.save()

        content = config.cfg_file_path.read_text()
        # Check that the YAML file lines don't contain "name:" (only "cfg_class_name:")
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                assert not stripped.startswith("name:"), (
                    f"Found 'name:' in line: {line}"
                )
                assert not stripped.startswith("cfg_file_path:"), (
                    f"Found 'cfg_file_path:' in line: {line}"
                )
        # cfg_class_name should be included
        assert "cfg_class_name:" in content
        assert "SimpleConfig" in content


class TestConfiguredClassName:
    """Test configured_class_name field."""

    def test_configured_class_name_defaults_to_none(self):
        """configured_class_name defaults to None."""
        config = GPConfig()
        assert config.configured_class_name is None

    def test_configured_class_name_can_be_set(self):
        """configured_class_name can be set during initialization."""
        config = GPConfig(configured_class_name="Database")
        assert config.configured_class_name == "Database"


class TestConfiguredClassRemoved:
    """Test that configured_class ClassVar no longer exists."""

    def test_configured_class_does_not_exist(self):
        """configured_class ClassVar should not exist."""
        # Check that configured_class is not defined as a ClassVar on GPConfig
        # It should either not exist, or be None (which means it wasn't explicitly defined)
        assert not hasattr(GPConfig, "configured_class")

    def test_configured_class_not_in_class_annotations(self):
        """configured_class should not be in class annotations."""
        # Check that configured_class is not in the class annotations
        # This ensures it's not defined as a ClassVar
        from typing import get_type_hints

        hints = get_type_hints(GPConfig, include_extras=True)
        assert "configured_class" not in hints


class TestSaveIncludesConfiguredClassName:
    """Test that save() includes configured_class_name when set."""

    def test_save_includes_configured_class_name_when_set(self, tmp_path: Path):
        """save() includes configured_class_name in YAML when set."""
        import yaml

        config = GPConfig(configured_class_name="Database")
        config.name = "test_config"
        config.cfg_file_path = tmp_path / "test_config.yaml"
        config.save()

        with open(config.cfg_file_path, "r", encoding="utf-8") as f:
            saved_data = yaml.safe_load(f)

        assert "configured_class_name" in saved_data
        assert saved_data["configured_class_name"] == "Database"

    def test_save_excludes_configured_class_name_when_none(self, tmp_path: Path):
        """save() does not include configured_class_name when None."""
        import yaml

        config = GPConfig()
        config.name = "test_config"
        config.cfg_file_path = tmp_path / "test_config.yaml"
        config.save()

        with open(config.cfg_file_path, "r", encoding="utf-8") as f:
            saved_data = yaml.safe_load(f)

        # configured_class_name should NOT be in saved data when None
        assert "configured_class_name" not in saved_data


class ServiceConfig(GPConfig):
    """Test config with business fields and a non-default cfg_class_name."""

    cfg_class_name: ClassVar[str] = "ServiceConfig"
    service_host: str = "0.0.0.0"
    service_port: int = 5432
    enabled: bool = True


class TestSaveMetadataHandling:
    """Regression tests locking in save() metadata-field handling.

    These pin the byte-identity contract: metadata fields are excluded from the
    dump uniformly and added back by explicit rule.
    """

    def test_save_includes_configured_class_name_when_set(self, tmp_path: Path):
        """configured_class_name set → present in YAML with its value."""
        config = ServiceConfig(configured_class_name="MyService")
        config.cfg_file_path = tmp_path / "service.yaml"
        config.save()

        content = config.cfg_file_path.read_text(encoding="utf-8")
        assert "configured_class_name: MyService" in content

    def test_save_omits_configured_class_name_when_none(self, tmp_path: Path):
        """configured_class_name None → no configured_class_name key at all.

        Guards against a `configured_class_name: null` line being written.
        """
        config = ServiceConfig()
        config.cfg_file_path = tmp_path / "service.yaml"
        config.save()

        content = config.cfg_file_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            assert not stripped.startswith("configured_class_name:"), (
                f"Found configured_class_name line in YAML: {line!r}"
            )

    def test_save_preserves_cfg_class_name(self, tmp_path: Path):
        """cfg_class_name ClassVar is always written to YAML."""
        config = ServiceConfig()
        config.cfg_file_path = tmp_path / "service.yaml"
        config.save()

        content = config.cfg_file_path.read_text(encoding="utf-8")
        assert "cfg_class_name: ServiceConfig" in content

    def test_save_excludes_name_path_and_readonly(self, tmp_path: Path):
        """name, cfg_file_path, readonly must never appear in the saved YAML."""
        config = ServiceConfig(readonly=True)
        config.name = "should_not_leak"
        config.cfg_file_path = tmp_path / "service.yaml"
        config.readonly = False  # allow save
        config.save()

        content = config.cfg_file_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            assert not stripped.startswith("name:"), f"Found 'name:' line: {line!r}"
            assert not stripped.startswith("cfg_file_path:"), (
                f"Found 'cfg_file_path:' line: {line!r}"
            )
            assert not stripped.startswith("readonly:"), (
                f"Found 'readonly:' line: {line!r}"
            )

    def test_save_preserves_business_fields(self, tmp_path: Path):
        """Business fields round-trip into the YAML with their values."""
        config = ServiceConfig(
            service_host="db.internal", service_port=6543, enabled=False
        )
        config.cfg_file_path = tmp_path / "service.yaml"
        config.save()

        content = config.cfg_file_path.read_text(encoding="utf-8")
        assert "service_host: db.internal" in content
        assert "service_port: 6543" in content
        assert "enabled: false" in content

    def test_round_trip_save_and_reload(self, tmp_path: Path):
        """Save then reload yields a config with matching field values."""
        import yaml

        original = ServiceConfig(
            service_host="cache.internal",
            service_port=11211,
            enabled=True,
            configured_class_name="MemcachedService",
        )
        original.cfg_file_path = tmp_path / "service.yaml"
        original.save()

        # Reload the same way the manager does: parse YAML, drop the ClassVar
        # cfg_class_name, then construct the config from the remaining fields.
        with open(original.cfg_file_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
        data_for_config = {
            k: v for k, v in raw_data.items() if k != "cfg_class_name"
        }
        reloaded = ServiceConfig(**data_for_config)

        assert reloaded.service_host == original.service_host
        assert reloaded.service_port == original.service_port
        assert reloaded.enabled == original.enabled
        assert reloaded.cfg_class_name == original.cfg_class_name
        assert reloaded.configured_class_name == original.configured_class_name
