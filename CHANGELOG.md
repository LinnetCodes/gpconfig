# Changelog

All notable changes to gpconfig are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.4] - 2026-07-14

**Error-message enhancement release.** No public API or behaviour changes — this
version improves the diagnostic information carried by exceptions raised while
loading YAML config files, so users can locate the source of config errors more
quickly. Exception class signatures are unchanged.

### Changed
- YAML syntax/parse errors (bad indentation, unclosed quotes/brackets, etc.) are now caught in `_load_yaml_dict` and wrapped as `ConfigValidationError` instead of escaping as a raw `yaml.YAMLError` with no config-file context. PyYAML embeds the file path, line, and column in the error message, so the wrapped exception surfaces the full location (`str(error)` carries the dotted config path via `.path`, plus the on-disk file path and line/column).
- The non-dict top-level `ConfigValidationError` message now embeds the on-disk file path (previously only described the type mismatch), so users can locate the file even when only a dotted logical path was passed.
- `ConfigValidationError` raised from Pydantic `ValidationError` in `get_config` now embeds the on-disk file path alongside Pydantic's field-level detail. The original `ValidationError` is preserved as `__cause__` and on `.original_error` for programmatic access.

## [0.3.3] - 2026-07-05

**The first Beta release.** This version addresses all findings from a comprehensive
code review: security hardening (path validation, cfg_folder containment), fail-early
validation (`__init_subclass__`, project_name collision detection), cache consistency,
and documentation completeness. See the sections below for details.

### Added
- `IllegalPathError` exception (in `gpconfig.exceptions`, exported from `gpconfig`): raised when a config path is malformed (empty, dots-only, consecutive dots, leading/trailing dot, or a literal `/`/`\` in cfg_path style) or escapes `cfg_folder`. Carries a `path` attribute holding the offending path string.
- `GPConfigManager.reset_registries()` classmethod: clears both `_config_classes` and `_configurable_classes` (public API for test teardown and re-initialisation).
- `GPConfigManager.invalidate_cache(path=None)`: clears the config cache (all entries, or one file's entry by path). The cache is a snapshot tied to the manager instance's lifetime; call this after external file modifications.
- `GPConfig.__init_subclass__`: validates `default_cfg_path` at subclass-definition time (fail-early). Rejects values containing `.` (`ValueError`) or non-string types (`TypeError`).
- `GPConfigManager` and `GPConfigFolder` now define `__repr__` for easier debugging.
- Documentation: plaintext-storage warning, cache snapshot semantics with `invalidate_cache` guidance, and the `project_name` / subdirectory collision constraint.

### Changed
- **BREAKING:** `GPConfigManager.save(config, path=...)` — `path` is now a **folder path** (file-system style, `/` or `\` separated), semantically identical to `GPConfig.default_cfg_path`. The file is always named `{config.name}.yaml` inside that folder. Previously `path` was treated as the full extensionless file path. `path` must not contain `.` (this rejects cfg_path style, `.yaml` suffixes, and `..` traversal in one check). Migration: pass the destination **folder**, not the full file path.
- **BREAKING:** `GPConfigManager.global_env` property now returns a read-only `MappingProxyType` view instead of a mutable `dict`. Item mutation (`mgr.global_env[k] = v`, `del`) raises `TypeError`; absent mutating methods (`.pop()`, `.update()`) raise `AttributeError`. For a mutable copy: `dict(mgr.global_env)`.
- **BREAKING:** `GPConfigManager.__init__` now raises `ConfigFolderError` if `cfg_folder` contains a top-level subdirectory whose name equals `project_name` (prevents the optional `project_name` path prefix from shadowing that subdirectory).
- **BREAKING:** `get_config("")` now raises `IllegalPathError` (previously returned the root `GPConfigFolder`).
- **BREAKING:** `get_config("global_env.")` (trailing dot) now raises `IllegalPathError` (previously returned the entire `global_env` dict — a bug).
- `get_config`, `list_configs`, and `get_object` now validate paths via `_normalize_path` and raise `IllegalPathError` for malformed paths (previously `ConfigNotFoundError` or undefined behaviour).
- Non-dict YAML top-level now raises `ConfigValidationError` (previously a bare `AttributeError`).
- `save()` now caches the saved config, for consistency with `get_config`'s cache.
- `TypeVar("T")` is now bound to `GPConfig` for better static type checking.
- `yaml.safe_load` calls are wrapped so that a `FileNotFoundError` (TOCTOU between `exists()` and `open()`) is converted into `ConfigNotFoundError`.

### Fixed
- Cache consistency: `get_config` with a key path (e.g. `get_config("database.port")`) now caches the config on first access. Previously it re-read the file from disk on every key-path access.
- `save()`'s `configured_class_name` round-trip: the exclude logic is now uniform (the previous dump-then-pop pattern could leak the field in some cases).

### Documentation
- Documented `IllegalPathError` (hierarchy, attributes, raised-by, examples) in both EN and ZH exception references, and added it to the index exception tables and the `get_config` / `save` API docs.
- Documented the read-only `global_env` contract (`MappingProxyType`, mutation errors, `dict(...)` copy) in both EN and ZH manager references.
- Documented the `default_cfg_path` folder-path contract and `__init_subclass__` fail-early validation in both EN and ZH GPConfig references.

[Unreleased]: https://github.com/LinnetCodes/gpconfig/compare/version-0.3.4...HEAD
[0.3.4]: https://github.com/LinnetCodes/gpconfig/releases/tag/version-0.3.4
[0.3.3]: https://github.com/LinnetCodes/gpconfig/releases/tag/version-0.3.3
