"""Tests for GPConfigManager caching behaviour and invalidate_cache().

Covers Task 5 (finding 3.2):
- Key-path access now populates the cache.
- Repeated key access does not re-read disk (snapshot semantics).
- invalidate_cache() clears all / one / no-op / forces reload.
- The raw-dict cache path (no registered config class) also caches.
"""

import time
from pathlib import Path
from typing import ClassVar

import pytest

from gpconfig.config import GPConfig
from gpconfig.manager import GPConfigManager


class ServiceConfig(GPConfig):
    """Test config with a registered cfg_class_name."""

    cfg_class_name: ClassVar[str] = "TestCachingServiceConfig"
    port: int = 8080
    host: str = "localhost"


class OtherConfig(GPConfig):
    """A second registered config to populate a second cache entry."""

    cfg_class_name: ClassVar[str] = "TestCachingOtherConfig"
    value: int = 1


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset class-level registries before each test."""
    GPConfigManager.reset_registries()
    yield
    GPConfigManager.reset_registries()


def _make_cfg_folder(tmp_path: Path) -> Path:
    """Create a minimal cfg folder with global_env + svc.yaml."""
    (tmp_path / "global_env.yaml").write_text("version: 1.0\ndebug: true\n")
    (tmp_path / "svc.yaml").write_text("cfg_class_name: TestCachingServiceConfig\nport: 8080\nhost: localhost\n")
    (tmp_path / "other.yaml").write_text("cfg_class_name: TestCachingOtherConfig\nvalue: 1\n")
    return tmp_path


@pytest.fixture
def manager(tmp_path: Path) -> GPConfigManager:
    """Create a manager with registered classes and a populated cfg folder."""
    GPConfigManager.register_config_class(ServiceConfig)
    GPConfigManager.register_config_class(OtherConfig)
    return GPConfigManager("testproject", cfg_folder=_make_cfg_folder(tmp_path))


class TestKeyAccessCaches:
    """Part A: key-path access now populates the cache."""

    def test_key_access_populates_cache(self, manager):
        """Calling get_config with a key path caches the underlying object.

        After get_config('svc.port'), a subsequent full get_config('svc') must
        return the SAME cached object (object identity), proving the key access
        populated the cache.
        """
        # Key access first.
        port = manager.get_config("svc.port")
        assert port == 8080

        # Cache must now contain the svc file's entry.
        svc_key = str(manager.cfg_folder / "svc.yaml")
        assert svc_key in manager._config_cache

        # Full access returns the same cached object.
        full_config = manager.get_config("svc")
        assert isinstance(full_config, ServiceConfig)

        cached_obj = manager._config_cache[svc_key]
        assert full_config is cached_obj

    def test_repeated_key_access_does_not_reread_disk(self, manager, tmp_path):
        """Repeated key access hits the cache: a disk mutation is NOT seen.

        1. get_config('svc.port') -> 8080 (loads + caches).
        2. get_config('svc.port') again -> still 8080 (cache hit).
        3. Mutate the file on disk to 9999.
        4. get_config('svc.port') -> STILL 8080 (proves cache, not disk, was hit).
        """
        assert manager.get_config("svc.port") == 8080
        assert manager.get_config("svc.port") == 8080

        # Mutate the file on disk.
        svc_path = manager.cfg_folder / "svc.yaml"
        time.sleep(0.01)  # ensure mtime change on coarse-grained filesystems
        svc_path.write_text(
            "cfg_class_name: TestCachingServiceConfig\nport: 9999\nhost: localhost\n"
        )

        # Cache hit -> stale value returned.
        assert manager.get_config("svc.port") == 8080


class TestInvalidateCache:
    """Part B: invalidate_cache() public method."""

    def test_invalidate_no_args_clears_all(self, manager):
        """invalidate_cache() with no args clears the entire cache."""
        manager.get_config("svc")
        manager.get_config("other")
        assert len(manager._config_cache) >= 2

        manager.invalidate_cache()

        assert manager._config_cache == {}

    def test_invalidate_path_clears_one_entry(self, manager):
        """invalidate_cache(path) clears only that file's entry."""
        manager.get_config("svc")
        manager.get_config("other")
        svc_key = str(manager.cfg_folder / "svc.yaml")
        other_key = str(manager.cfg_folder / "other.yaml")
        assert svc_key in manager._config_cache
        assert other_key in manager._config_cache

        manager.invalidate_cache("svc")

        assert svc_key not in manager._config_cache
        assert other_key in manager._config_cache

    def test_invalidate_unknown_path_is_noop(self, manager):
        """invalidate_cache(unknown_path) does not raise and is a no-op."""
        manager.get_config("svc")
        before = dict(manager._config_cache)

        # Well-formed path that doesn't resolve to a file -> no-op, no raise.
        manager.invalidate_cache("does.not.exist")

        assert manager._config_cache == before

    def test_invalidate_forces_reload(self, manager, tmp_path):
        """After invalidate_cache(), the next get_config re-reads disk."""
        assert manager.get_config("svc.port") == 8080

        # Mutate on disk.
        svc_path = manager.cfg_folder / "svc.yaml"
        time.sleep(0.01)
        svc_path.write_text(
            "cfg_class_name: TestCachingServiceConfig\nport: 9999\nhost: localhost\n"
        )

        # Without invalidation, stale value is served.
        assert manager.get_config("svc.port") == 8080

        # After invalidation, the new value is read from disk.
        manager.invalidate_cache()
        assert manager.get_config("svc.port") == 9999


class TestDictCache:
    """Regression: a file with no registered class returns a dict that is cached."""

    def test_dict_is_cached(self, tmp_path):
        """A file without a registered config class returns a dict, also cached.

        Key access after a full (dict) access must hit the same cached dict,
        not re-read disk.
        """
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        # No cfg_class_name -> no registered class -> raw dict.
        (tmp_path / "raw.yaml").write_text("alpha: 1\nbeta:\n  gamma: 2\n")

        mgr = GPConfigManager("testproject", cfg_folder=tmp_path)

        # Full access -> raw dict cached.
        full = mgr.get_config("raw")
        assert isinstance(full, dict)
        raw_key = str(mgr.cfg_folder / "raw.yaml")
        assert raw_key in mgr._config_cache
        assert mgr._config_cache[raw_key] is full

        # Key access resolves against the cached dict.
        gamma = mgr.get_config("raw.beta.gamma")
        assert gamma == 2

        # A subsequent full access returns the SAME cached dict object.
        assert mgr.get_config("raw") is full

    def test_dict_key_access_caches(self, tmp_path):
        """Key access on a dict-only file populates the cache (no re-read)."""
        (tmp_path / "global_env.yaml").write_text("version: 1.0\n")
        (tmp_path / "raw.yaml").write_text("alpha: 1\n")

        mgr = GPConfigManager("testproject", cfg_folder=tmp_path)

        # Key access first.
        assert mgr.get_config("raw.alpha") == 1

        # Cache now populated with the dict.
        raw_key = str(mgr.cfg_folder / "raw.yaml")
        assert raw_key in mgr._config_cache
        assert isinstance(mgr._config_cache[raw_key], dict)

        # Mutate disk; cached value still served.
        time.sleep(0.01)
        (tmp_path / "raw.yaml").write_text("alpha: 999\n")
        assert mgr.get_config("raw.alpha") == 1
