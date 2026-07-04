"""Tests for GPConfigManager initialization and config folder resolution."""

import pytest
from pathlib import Path
from unittest.mock import patch

from gpconfig.manager import GPConfigManager
from gpconfig.exceptions import ConfigFolderError


class TestGPConfigManagerInit:
    """Test GPConfigManager initialization."""

    def test_init_with_explicit_folder(self, tmp_path: Path):
        """Test initialization with explicit config folder."""
        # Create required global_env.yaml
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")

        manager = GPConfigManager("testproject", cfg_folder=tmp_path)

        assert manager.project_name == "testproject"
        assert manager.cfg_folder == tmp_path.resolve()

    def test_init_raises_when_folder_missing(self, tmp_path: Path):
        """Test that initialization raises when folder doesn't exist."""
        non_existent = tmp_path / "nonexistent"

        with pytest.raises(ConfigFolderError) as exc_info:
            GPConfigManager("testproject", cfg_folder=non_existent)

        assert "config folder" in str(exc_info.value).lower()

    def test_init_raises_when_global_env_missing(self, tmp_path: Path):
        """Test that initialization raises when global_env.yaml is missing."""
        # Create folder but no global_env.yaml
        tmp_path.mkdir(exist_ok=True)

        with pytest.raises(ConfigFolderError) as exc_info:
            GPConfigManager("testproject", cfg_folder=tmp_path)

        assert "global_env.yaml" in str(exc_info.value)


class TestConfigFolderResolution:
    """Test config folder search rules."""

    def test_uses_explicit_path_over_env_var(self, tmp_path: Path, monkeypatch):
        """Explicit path takes precedence over environment variable."""
        # Setup explicit folder
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")

        # Setup env var folder (different location)
        env_folder = tmp_path.parent / "env_folder"
        env_folder.mkdir(exist_ok=True)
        (env_folder / "global_env.yaml").write_text("version: 2.0\n")
        monkeypatch.setenv("TESTPROJECT_CFG_PATH", str(env_folder))

        manager = GPConfigManager("testproject", cfg_folder=tmp_path)
        assert manager.cfg_folder == tmp_path.resolve()

    def test_uses_env_var_when_no_explicit_path(self, tmp_path: Path, monkeypatch):
        """Environment variable is used when no explicit path."""
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        monkeypatch.setenv("MYPROJECT_CFG_PATH", str(tmp_path))

        manager = GPConfigManager("myproject")
        assert manager.cfg_folder == tmp_path.resolve()

    def test_uses_home_folder_when_no_explicit_or_env(
        self, tmp_path: Path, monkeypatch
    ):
        """User home subfolder is used when no explicit path or env var."""
        # Setup home folder
        home_configs = tmp_path / "home_configs"
        project_folder = home_configs / ".myapp"
        project_folder.mkdir(parents=True)
        (project_folder / "global_env.yaml").write_text("version: 1.0\n")

        # Mock Path.home() to return our test folder
        with patch.object(Path, "home", return_value=home_configs):
            manager = GPConfigManager("myapp")
            assert manager.cfg_folder == project_folder.resolve()

    def test_raises_when_no_valid_folder_found(self, monkeypatch):
        """Raises error when no valid config folder can be found."""
        # Remove all possible paths
        monkeypatch.delenv("MYPROJECT_CFG_PATH", raising=False)

        with patch.object(Path, "home", return_value=Path("/nonexistent")):
            with pytest.raises(ConfigFolderError) as exc_info:
                GPConfigManager("myproject")

            assert "Could not find valid config folder" in str(exc_info.value)


class TestGlobalEnvLoading:
    """Test global_env loading during initialization."""

    def test_loads_global_env_dict(self, tmp_path: Path):
        """Test that global_env is loaded as a dict."""
        (tmp_path / "global_env.yaml").write_text("version: 1.0\ndebug: true\n")

        manager = GPConfigManager("testproject", cfg_folder=tmp_path)

        assert manager.global_env == {"version": 1.0, "debug": True}

    def test_global_env_empty_when_file_empty(self, tmp_path: Path):
        """Test that global_env is empty dict when file is empty."""
        (tmp_path / "global_env.yaml").write_text("")

        manager = GPConfigManager("testproject", cfg_folder=tmp_path)

        assert manager.global_env == {}

    def test_global_env_empty_when_file_has_only_comments(self, tmp_path: Path):
        """Test that global_env is empty dict when file has only comments."""
        (tmp_path / "global_env.yaml").write_text(
            "# Just a comment\n# Another comment\n"
        )

        manager = GPConfigManager("testproject", cfg_folder=tmp_path)

        assert manager.global_env == {}


class TestProjectNameCollision:
    """Test fail-early detection of a config subdirectory named after project_name.

    The optional project_name path prefix (e.g. get_config("myapp.x")) would
    shadow a same-named top-level subdirectory, making it unreachable via
    dot-notation. Construction must reject this layout.
    """

    def test_collision_raises(self, tmp_path: Path):
        """A subdir named exactly after project_name raises ConfigFolderError."""
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        # Subdirectory whose name equals project_name, with content inside.
        collision_dir = tmp_path / "myapp"
        collision_dir.mkdir()
        (collision_dir / "stuff.yaml").write_text("key: value\n")

        with pytest.raises(ConfigFolderError) as exc_info:
            GPConfigManager("myapp", cfg_folder=tmp_path)

        message = str(exc_info.value)
        # Message should mention project_name and the remedy (rename).
        assert "myapp" in message
        assert "Rename" in message or "rename" in message

    def test_empty_collision_subdir_also_raises(self, tmp_path: Path):
        """An empty collision subdir still raises (strict fail-early)."""
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        # Empty subdirectory named after project_name.
        (tmp_path / "myapp").mkdir()

        with pytest.raises(ConfigFolderError) as exc_info:
            GPConfigManager("myapp", cfg_folder=tmp_path)

        assert "myapp" in str(exc_info.value)

    def test_no_collision_unrelated_subdirs_works(self, tmp_path: Path):
        """Unrelated subdir names construct successfully."""
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        (tmp_path / "database").mkdir()
        (tmp_path / "database" / "pg.yaml").write_text("host: localhost\n")

        manager = GPConfigManager("myapp", cfg_folder=tmp_path)

        assert manager.project_name == "myapp"
        assert manager.cfg_folder == tmp_path.resolve()

    def test_cfg_folder_itself_named_after_project_name_is_fine(
        self, tmp_path: Path
    ):
        """cfg_folder's own name being project_name does NOT trigger (not a child)."""
        # cfg_folder itself is named 'myapp'.
        cfg_folder = tmp_path / "myapp"
        cfg_folder.mkdir()
        (cfg_folder / "global_env.yaml").write_text("version: 1.0\n")
        (cfg_folder / "database").mkdir()
        (cfg_folder / "database" / "pg.yaml").write_text("host: localhost\n")

        manager = GPConfigManager("myapp", cfg_folder=cfg_folder)

        assert manager.cfg_folder == cfg_folder.resolve()

    def test_no_collision_multiple_differently_named_subdirs(self, tmp_path: Path):
        """Multiple subdirs all named differently from project_name are fine."""
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        for name in ("database", "cache", "llm"):
            sub = tmp_path / name
            sub.mkdir()
            (sub / "x.yaml").write_text("k: v\n")

        manager = GPConfigManager("myapp", cfg_folder=tmp_path)

        assert manager.project_name == "myapp"
