"""Tests for YAML loading via GPConfigManager._load_yaml_dict.

Covers the consolidation of YAML loading, type validation, and
TOCTOU-safe file reading (review findings 2.1 and 4.1).
"""

import pytest
from pathlib import Path

from gpconfig.manager import GPConfigManager
from gpconfig.exceptions import ConfigNotFoundError, ConfigValidationError


class TestLoadYamlDictDirect:
    """Directly exercise the _load_yaml_dict helper."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> GPConfigManager:
        """Create a minimal manager pointing at an empty-ish config folder."""
        (tmp_path / "global_env.yaml").write_text("debug: true\n")
        return GPConfigManager("testproject", cfg_folder=tmp_path)

    def test_missing_file_raises_config_not_found(self, manager, tmp_path):
        """_load_yaml_dict raises ConfigNotFoundError for a vanished file.

        This exercises the TOCTOU branch (FileNotFoundError -> ConfigNotFoundError)
        without mocking open(): the file simply never existed.
        """
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(ConfigNotFoundError) as exc_info:
            manager._load_yaml_dict(missing, str(missing))

        # The path_for_error string must be embedded in the message.
        assert str(missing) in str(exc_info.value)

    def test_dict_yaml_loads(self, manager, tmp_path):
        """_load_yaml_dict returns the dict for a normal mapping YAML."""
        f = tmp_path / "db.yaml"
        f.write_text("host: localhost\nport: 5432\n", encoding="utf-8")
        result = manager._load_yaml_dict(f, str(f))
        assert result == {"host": "localhost", "port": 5432}

    def test_empty_yaml_returns_empty_dict(self, manager, tmp_path):
        """_load_yaml_dict returns {} for an empty file."""
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")
        assert manager._load_yaml_dict(f, str(f)) == {}

    def test_comments_only_yaml_returns_empty_dict(self, manager, tmp_path):
        """_load_yaml_dict returns {} for a comments-only file."""
        f = tmp_path / "comments.yaml"
        f.write_text("# just a comment\n# another\n", encoding="utf-8")
        assert manager._load_yaml_dict(f, str(f)) == {}

    def test_list_yaml_raises_validation_error(self, manager, tmp_path):
        """_load_yaml_dict raises ConfigValidationError for a top-level list."""
        f = tmp_path / "list.yaml"
        f.write_text("- foo\n- bar\n", encoding="utf-8")
        with pytest.raises(ConfigValidationError) as exc_info:
            manager._load_yaml_dict(f, "some.dotted.path")
        assert exc_info.value.path == "some.dotted.path"

    def test_scalar_yaml_raises_validation_error(self, manager, tmp_path):
        """_load_yaml_dict raises ConfigValidationError for a top-level scalar.

        Even when the caller passes only a dotted logical path (as get_config
        does), the file path must still appear in the message so users can
        locate the offending file on disk.
        """
        f = tmp_path / "scalar.yaml"
        f.write_text("just a string\n", encoding="utf-8")
        with pytest.raises(ConfigValidationError) as exc_info:
            manager._load_yaml_dict(f, "scalar")  # dotted name, not file path
        assert exc_info.value.path == "scalar"
        # File path must be present regardless of the logical path used.
        assert str(f) in str(exc_info.value)

    def test_malformed_yaml_raises_validation_error_with_path_and_line(
        self, manager, tmp_path
    ):
        """A YAML syntax error surfaces as ConfigValidationError carrying the
        dotted path, the file path, and a line number.

        Previously a syntax error escaped _load_yaml_dict as a raw yaml.YAMLError
        with no config-file context. PyYAML embeds the offending line/column in
        str(error) when loaded from a file, so the message should let users jump
        straight to the broken line.
        """
        f = tmp_path / "broken.yaml"
        # Unclosed flow-style mapping quote: a classic YAML scanner error.
        f.write_text('host: "localhost\nport: 5432\n', encoding="utf-8")
        with pytest.raises(ConfigValidationError) as exc_info:
            manager._load_yaml_dict(f, "broken")
        err = exc_info.value
        # Logical (dotted) path is carried on the exception for config lookup.
        assert err.path == "broken"
        msg = str(err)
        # File path must be present so the user can open the offending file.
        assert str(f) in msg
        # A line number should be present (PyYAML formats marks as "line X").
        assert "line" in msg

    def test_malformed_yaml_via_get_config_carries_path(self, manager, tmp_path):
        """get_config surfaces a YAML syntax error with the config name as path."""
        broken = tmp_path / "broken.yaml"
        broken.write_text("host: [unclosed\n", encoding="utf-8")
        with pytest.raises(ConfigValidationError) as exc_info:
            manager.get_config("broken")
        assert exc_info.value.path == "broken"
        assert str(broken) in str(exc_info.value)


class TestGetConfigYamlTypeValidation:
    """Validate that get_config surfaces non-dict YAML as ConfigValidationError.

    Regression for review finding 2.1: a list/scalar top level previously
    raised a bare AttributeError at raw_data.get("cfg_class_name").
    """

    @pytest.fixture
    def manager_with_list_yaml(self, tmp_path: Path) -> GPConfigManager:
        """Create a manager whose 'badlist.yaml' contains a YAML list."""
        (tmp_path / "global_env.yaml").write_text("debug: true\n")
        (tmp_path / "badlist.yaml").write_text("- foo\n- bar\n", encoding="utf-8")
        return GPConfigManager("testproject", cfg_folder=tmp_path)

    @pytest.fixture
    def manager_with_scalar_yaml(self, tmp_path: Path) -> GPConfigManager:
        """Create a manager whose 'badscalar.yaml' contains a YAML scalar."""
        (tmp_path / "global_env.yaml").write_text("debug: true\n")
        (tmp_path / "badscalar.yaml").write_text("just a string\n", encoding="utf-8")
        return GPConfigManager("testproject", cfg_folder=tmp_path)

    def test_list_yaml_raises_validation_error_not_attribute_error(
        self, manager_with_list_yaml
    ):
        """A list-typed YAML file raises ConfigValidationError, not AttributeError."""
        with pytest.raises(ConfigValidationError) as exc_info:
            manager_with_list_yaml.get_config("badlist")
        # The dotted path must be carried on the error.
        assert exc_info.value.path == "badlist"
        # Sanity: it must not be an AttributeError-derived error.
        assert not isinstance(exc_info.value, AttributeError)

    def test_scalar_yaml_raises_validation_error(self, manager_with_scalar_yaml):
        """A scalar-typed YAML file raises ConfigValidationError."""
        with pytest.raises(ConfigValidationError):
            manager_with_scalar_yaml.get_config("badscalar")


class TestGetConfigYamlRegression:
    """Regression coverage: normal and empty YAML still load correctly."""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> GPConfigManager:
        """Manager with a normal dict YAML and an empty YAML file."""
        (tmp_path / "global_env.yaml").write_text("debug: true\n")
        (tmp_path / "database.yaml").write_text(
            "host: localhost\nport: 5432\n", encoding="utf-8"
        )
        (tmp_path / "blank.yaml").write_text("", encoding="utf-8")
        return GPConfigManager("testproject", cfg_folder=tmp_path)

    def test_dict_yaml_loads_via_get_config(self, manager):
        """A normal dict YAML returns the raw dict (no registered class)."""
        result = manager.get_config("database")
        assert result == {"host": "localhost", "port": 5432}

    def test_empty_yaml_returns_empty_dict_via_get_config(self, manager):
        """An empty YAML file returns an empty dict from get_config."""
        result = manager.get_config("blank")
        assert result == {}
