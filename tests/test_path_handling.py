"""Tests for the unified path-handling system.

Covers code-review findings:
- 3.6: extracted ``_normalize_path`` helper (de-duplication).
- 2.2: ``_assert_within_cfg_folder`` containment check + ``IllegalPathError``.
- 4.3: rejection of 6 pathological path classes inside ``_normalize_path``.
"""

import pytest
from pathlib import Path

from gpconfig import GPConfigManager, IllegalPathError
from gpconfig.exceptions import ConfigNotFoundError


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset class-level registries before and after each test."""
    GPConfigManager._config_classes = {}
    GPConfigManager._configurable_classes = {}
    yield
    GPConfigManager._config_classes = {}
    GPConfigManager._configurable_classes = {}


@pytest.fixture
def manager(tmp_path: Path) -> GPConfigManager:
    """Create a manager with a small populated config folder (project=myapp)."""
    (tmp_path / "global_env.yaml").write_text("version: 1.0\ndebug: true\n")
    (tmp_path / "svc.yaml").write_text("port: 8080\n")

    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "inner.yaml").write_text("value: inner_value\n")

    return GPConfigManager("myapp", cfg_folder=tmp_path)


# ---------------------------------------------------------------------------
# Part C: _normalize_path rejects 6 pathological path classes
# ---------------------------------------------------------------------------


class TestNormalizePathRejectsPathological:
    """All 6 pathological path classes are rejected with IllegalPathError."""

    def test_empty_string_rejected(self, manager: GPConfigManager):
        """(a) empty string -> 'empty path'."""
        with pytest.raises(IllegalPathError) as exc_info:
            manager._normalize_path("")
        assert "empty path" in str(exc_info.value)

    @pytest.mark.parametrize("dots", [".", "..", "..."])
    def test_pure_dots_rejected(self, manager: GPConfigManager, dots: str):
        """(b) pure dots -> 'path consists only of dots'."""
        with pytest.raises(IllegalPathError) as exc_info:
            manager._normalize_path(dots)
        assert "only of dots" in str(exc_info.value)

    def test_consecutive_dots_rejected(self, manager: GPConfigManager):
        """(c) consecutive dots (empty middle segment) -> 'empty segment'."""
        with pytest.raises(IllegalPathError) as exc_info:
            manager._normalize_path("a..b")
        assert "empty segment" in str(exc_info.value)

    def test_leading_dot_rejected(self, manager: GPConfigManager):
        """(d) leading dot -> 'leading dot'."""
        with pytest.raises(IllegalPathError) as exc_info:
            manager._normalize_path(".x")
        assert "leading dot" in str(exc_info.value)

    def test_trailing_dot_rejected(self, manager: GPConfigManager):
        """(e) trailing dot -> 'trailing dot'."""
        with pytest.raises(IllegalPathError) as exc_info:
            manager._normalize_path("x.")
        assert "trailing dot" in str(exc_info.value)

    @pytest.mark.parametrize("bad", ["a/b", "a\\b"])
    def test_literal_slash_or_backslash_rejected(
        self, manager: GPConfigManager, bad: str
    ):
        """(f) literal '/' or '\\\\' -> rejected, use dot notation."""
        with pytest.raises(IllegalPathError) as exc_info:
            manager._normalize_path(bad)
        assert "literal" in str(exc_info.value)


class TestNormalizePathValidPaths:
    """Regression: valid paths still normalize correctly."""

    def test_simple_path(self, manager: GPConfigManager):
        """'svc' -> ['svc']."""
        assert manager._normalize_path("svc") == ["svc"]

    def test_dotted_path(self, manager: GPConfigManager):
        """'svc.port' -> ['svc', 'port']."""
        assert manager._normalize_path("svc.port") == ["svc", "port"]

    def test_project_name_prefix_stripped(self, manager: GPConfigManager):
        """'myapp.svc' (project_name=myapp) -> ['svc']."""
        assert manager._normalize_path("myapp.svc") == ["svc"]

    def test_nested_with_prefix_stripped(self, manager: GPConfigManager):
        """'myapp.subdir.inner' -> ['subdir', 'inner']."""
        assert manager._normalize_path("myapp.subdir.inner") == [
            "subdir",
            "inner",
        ]

    def test_error_carries_path_attribute(self, manager: GPConfigManager):
        """IllegalPathError stores the offending path on .path."""
        with pytest.raises(IllegalPathError) as exc_info:
            manager._normalize_path("a/b")
        assert exc_info.value.path == "a/b"


# ---------------------------------------------------------------------------
# Part B: _assert_within_cfg_folder
# ---------------------------------------------------------------------------


class TestAssertWithinCfgFolder:
    """Test the cfg_folder containment defence-in-depth check."""

    def test_path_inside_cfg_folder_ok(self, manager: GPConfigManager):
        """A resolved path inside cfg_folder does not raise."""
        inside = manager._cfg_folder / "svc.yaml"
        # Should not raise.
        manager._assert_within_cfg_folder(inside, "svc")

    def test_path_outside_cfg_folder_raises(self, manager: GPConfigManager):
        """A path outside cfg_folder raises IllegalPathError."""
        escape = manager._cfg_folder.parent / "escape.yaml"
        with pytest.raises(IllegalPathError) as exc_info:
            manager._assert_within_cfg_folder(escape, "escape")
        assert "escapes cfg_folder" in str(exc_info.value)
        assert exc_info.value.path == "escape"

    def test_cfg_folder_root_itself_ok(self, manager: GPConfigManager):
        """The cfg_folder root itself is considered inside (boundary case)."""
        manager._assert_within_cfg_folder(manager._cfg_folder, "")


# ---------------------------------------------------------------------------
# Integration: 3.6 + 4.3 combined via get_config
# ---------------------------------------------------------------------------


class TestGetConfigPathValidation:
    """End-to-end behaviour changes surfaced through get_config."""

    def test_empty_path_now_raises(self, manager: GPConfigManager):
        """get_config('') now raises IllegalPathError (was: root folder).

        Accepted behaviour change documented per the refactor decision.
        """
        with pytest.raises(IllegalPathError):
            manager.get_config("")

    def test_trailing_dot_now_raises(self, manager: GPConfigManager):
        """get_config('global_env.') now raises IllegalPathError (real bug fix).

        Previously this returned the entire global_env dict because the empty
        trailing segment was silently swallowed.
        """
        with pytest.raises(IllegalPathError):
            manager.get_config("global_env.")

    def test_valid_path_still_works(self, manager: GPConfigManager):
        """Regression guard: get_config('svc') still resolves the file."""
        value = manager.get_config("svc.port")
        assert value == 8080


# ---------------------------------------------------------------------------
# list_configs: empty-string sentinel + reuse of _check_folder_exists
# ---------------------------------------------------------------------------


class TestListConfigsPathHandling:
    """list_configs empty-string sentinel must keep working."""

    def test_empty_string_returns_root(self, manager: GPConfigManager):
        """list_configs('') returns root folder contents (root sentinel)."""
        items = manager.list_configs("")
        assert "svc" in items
        assert "subdir" in items
        assert "global_env" not in items

    def test_default_arg_returns_root(self, manager: GPConfigManager):
        """list_configs() (no arg) returns root folder contents."""
        items = manager.list_configs()
        assert "svc" in items

    def test_nonexistent_folder_raises(self, manager: GPConfigManager):
        """list_configs('nonexistent') raises ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError):
            manager.list_configs("nonexistent")

    def test_existing_subdir_returns_contents(self, manager: GPConfigManager):
        """Regression guard: list_configs('subdir') returns its contents."""
        assert manager.list_configs("subdir") == ["inner"]

    def test_project_name_prefix_now_stripped(self, manager: GPConfigManager):
        """Accepted change: list_configs('myapp.subdir') now strips the prefix.

        Previously list_configs did not understand the project_name prefix;
        now that it routes through _check_folder_exists -> _normalize_path
        the prefix is stripped like every other path API.
        """
        assert manager.list_configs("myapp.subdir") == ["inner"]

    def test_pathological_path_rejected(self, manager: GPConfigManager):
        """list_configs rejects pathological paths via _normalize_path."""
        with pytest.raises(IllegalPathError):
            manager.list_configs("a/b")
