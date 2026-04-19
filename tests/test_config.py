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
            default_cfg_path = "custom/default.yaml"
            value: str

        assert CustomConfig.default_cfg_path == "custom/default.yaml"


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
