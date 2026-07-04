"""Tests for API-safety hardening: read-only global_env, bound TypeVar, __repr__.

Covers review findings 4.2 (global_env immutability via MappingProxyType),
5.1 (bound TypeVar — runtime smoke test only), and 5.3 (__repr__ on both
GPConfigManager and GPConfigFolder).
"""

from pathlib import Path
from types import MappingProxyType

import pytest

from gpconfig.config import GPConfig
from gpconfig.manager import GPConfigFolder, GPConfigManager


class _SubConfig(GPConfig):
    """A GPConfig subclass for the bound-TypeVar smoke test."""

    value: str = "default"


@pytest.fixture
def manager(tmp_path: Path) -> GPConfigManager:
    """A manager with a populated global_env.yaml."""
    (tmp_path / "global_env.yaml").write_text("version: 1.0\ndebug: true\n")
    return GPConfigManager("testproject", cfg_folder=tmp_path)


class TestGlobalEnvReadOnly:
    """Finding 4.2: global_env must be a read-only view."""

    def test_global_env_is_mapping_proxy(self, manager: GPConfigManager):
        """global_env returns a MappingProxyType instance."""
        assert isinstance(manager.global_env, MappingProxyType)

    def test_global_env_reads_work(self, manager: GPConfigManager):
        """Reads through the proxy return the underlying values."""
        assert manager.global_env["debug"] is True
        assert manager.global_env.get("version") == 1.0

    def test_global_env_item_assignment_raises(self, manager: GPConfigManager):
        """Item assignment through the proxy raises TypeError."""
        with pytest.raises(TypeError):
            manager.global_env["new"] = "x"

    def test_global_env_item_delete_raises(self, manager: GPConfigManager):
        """Item deletion through the proxy raises TypeError."""
        with pytest.raises(TypeError):
            del manager.global_env["debug"]

    def test_global_env_pop_raises(self, manager: GPConfigManager):
        """pop() through the proxy raises (TypeError for item ops; pop itself
        is absent on MappingProxyType so AttributeError)."""
        with pytest.raises((TypeError, AttributeError)):
            manager.global_env.pop("debug")

    def test_global_env_mutation_does_not_touch_internal_state(
        self, manager: GPConfigManager
    ):
        """Crucial regression: a caught mutation must NOT change _global_env."""
        snapshot = dict(manager._global_env)
        for attempt in (
            lambda: manager.global_env.__setitem__("new", "x"),
            lambda: manager.global_env.__delitem__("debug"),
            lambda: manager.global_env.pop("debug"),
            lambda: manager.global_env.update({"x": 1}),
        ):
            with pytest.raises((TypeError, AttributeError)):
                attempt()
        assert manager._global_env == snapshot
        assert "new" not in manager._global_env
        assert manager._global_env["debug"] is True

    def test_global_env_returns_fresh_view_each_call(self, manager: GPConfigManager):
        """Each access returns a live read-only view (reflects underlying data)."""
        view_a = manager.global_env
        view_b = manager.global_env
        # Views are independent proxy objects but reflect the same underlying dict.
        assert isinstance(view_a, MappingProxyType)
        assert isinstance(view_b, MappingProxyType)
        assert view_a == view_b


class TestBoundTypeVar:
    """Finding 5.1: TypeVar bound to GPConfig (runtime smoke test only).

    Python does not enforce TypeVar bounds at runtime, so we cannot test the
    rejection of invalid config_cls. We only verify valid usage still works.
    """

    def test_get_config_with_gpconfig_subclass(self, manager: GPConfigManager):
        """get_config with a GPConfig subclass still works (regression)."""
        cfg_file = manager.cfg_folder / "thing.yaml"
        cfg_file.write_text("value: hello\n")
        config = manager.get_config("thing", config_cls=_SubConfig)
        assert isinstance(config, _SubConfig)
        assert config.value == "hello"


class TestRepr:
    """Finding 5.3: concise __repr__ on both classes."""

    def test_manager_repr_contains_class_name_and_fields(
        self, manager: GPConfigManager
    ):
        """repr(manager) names the class and the identifying fields."""
        text = repr(manager)
        assert "GPConfigManager(" in text
        assert "testproject" in text
        # cfg_folder is the resolved tmp_path; repr includes it. Path's repr and
        # str() can differ in separators on Windows, so compare via the Path's
        # own str() form (forward slashes in repr on all platforms).
        assert manager.cfg_folder.as_posix() in text

    def test_manager_repr_excludes_internal_caches(self, manager: GPConfigManager):
        """Internal caches (_config_cache, _folder_cache) are not in repr."""
        text = repr(manager)
        assert "_config_cache" not in text
        assert "_folder_cache" not in text

    def test_folder_repr_contains_class_name_and_path(
        self, manager: GPConfigManager
    ):
        """repr(folder) names the class and the relative_path."""
        (manager.cfg_folder / "subdir").mkdir()
        folder = manager.get_config("subdir")
        assert isinstance(folder, GPConfigFolder)
        text = repr(folder)
        assert "GPConfigFolder(" in text
        assert "subdir" in text

    def test_folder_repr_excludes_manager_backref(self, manager: GPConfigManager):
        """repr(folder) must not include _manager (no recursion)."""
        (manager.cfg_folder / "subdir").mkdir()
        folder = manager.get_config("subdir")
        text = repr(folder)
        assert "_manager" not in text
        assert "GPConfigManager" not in text

    def test_folder_repr_is_short(self, manager: GPConfigManager):
        """repr(folder) is short and not deeply nested (no recursion)."""
        (manager.cfg_folder / "subdir").mkdir()
        folder = manager.get_config("subdir")
        text = repr(folder)
        # A short repr is well under 200 chars; a recursing repr would be far longer.
        assert len(text) < 200
