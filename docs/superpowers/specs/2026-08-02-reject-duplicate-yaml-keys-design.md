# Reject Duplicate YAML Keys Design

**Status:** Approved

**Target release:** 0.3.5

**Date:** 2026-08-02

## Context

`GPConfigManager._load_yaml_dict()` currently calls `yaml.safe_load()`. PyYAML
6.0.3 silently overwrites an earlier value when two keys in the same YAML
mapping resolve to the same Python dictionary key. The loss happens before
Pydantic receives the parsed data, so schema validation cannot detect it.

The behavior is reproducible for top-level and nested mappings, mappings inside
lists, and `global_env.yaml`, because all of those inputs pass through
`_load_yaml_dict()`. PyYAML's upstream duplicate-key issue remains open, and the
latest released and main-branch mapping constructors still assign
`mapping[key] = value` without a duplicate check:

- <https://github.com/yaml/pyyaml/issues/165>
- <https://github.com/yaml/pyyaml/blob/main/lib/yaml/constructor.py>

The repository's pre-change baseline is 262 passing tests on PyYAML 6.0.3.

## Goals

- Reject duplicate explicit keys in every mapping loaded through
  `GPConfigManager._load_yaml_dict()` before conversion to an ordinary `dict`.
- Apply the check at arbitrary nesting depth, including mappings inside lists.
- Apply identical behavior to ordinary config files and `global_env.yaml`.
- Treat differently written keys as duplicates when PyYAML resolves them to
  equal Python keys, including `1` and `true`, or `null` and `~`.
- Raise the existing public `ConfigValidationError`, preserving the underlying
  YAML exception as both `original_error` and `__cause__`.
- Include the file path, duplicate key, first definition position, and repeated
  definition position in the diagnostic.
- Preserve the behavior and parsed result of all legal YAML, including merge
  keys.
- Continue to use PyYAML's safe loading capability.

## Non-goals

- Add business-schema validation to the YAML loading layer.
- Detect the same key used in different mapping nodes.
- Detect duplicate values.
- Add Portfolio-specific behavior.
- Merge, rename, repair, retry, or silently overwrite duplicate explicit keys.
- Add a compatibility switch for the former last-value-wins behavior.
- Change `GPConfig.save()`, `GPConfigManager.save()`, caching, or object
  construction.
- Expand or redefine YAML merge-key (`<<`) semantics.
- Add a new public exception or another YAML dependency.

## Selected Approach

Add a focused private module, `src/gpconfig/_yaml.py`, that extends
`yaml.SafeLoader` only at the mapping-construction boundary. This keeps parsing
policy separate from the already large manager module, performs one YAML parse,
and retains PyYAML as the parser and resolver.

The alternatives were rejected for the following reasons:

- Placing the custom loader in `manager.py` would minimize the file count but
  further mix YAML internals with path resolution, caching, and object loading.
- Composing and scanning a node tree before a second `safe_load()` would parse
  every file twice and duplicate more of PyYAML's alias, tag, and merge
  semantics.
- Replacing PyYAML or adding another parser would expand dependencies and alter
  behavior beyond this bug fix.

## Architecture

### Private YAML loading module

`src/gpconfig/_yaml.py` will contain:

- `_RejectDuplicateKeysSafeLoader`, a private subclass of `yaml.SafeLoader`.
- A private mapping constructor registered only on that subclass for PyYAML's
  default mapping tag.
- `load_yaml(stream: TextIO) -> Any`, the private-module loading entry point.

The module will call `yaml.load(stream, Loader=_RejectDuplicateKeysSafeLoader)`.
Although the function is named `yaml.load`, the supplied loader controls the
available constructors. Because the custom loader inherits `SafeLoader` and
adds only a mapping constructor, it does not enable Python-object construction
or otherwise broaden the safe input language.

The constructor will process each mapping as follows:

1. Snapshot the mapping's explicit key nodes before merge expansion, excluding
   nodes tagged as YAML merge keys.
2. Invoke PyYAML's existing `flatten_mapping()` so merge aliases and special
   value tags retain their established behavior.
3. Construct each snapshotted key with the same safe loader and compare the
   resulting hashable Python keys using normal dictionary equality. This catches
   both textually identical keys and textual variants that would collide in the
   resulting dictionary.
4. If a key was already seen in this mapping, raise
   `yaml.constructor.ConstructorError`. Its context mark identifies the first
   key node and its problem mark identifies the repeated key node.
5. If no duplicate exists, delegate mapping construction to PyYAML's existing
   `SafeLoader` implementation. Unhashable keys continue through the existing
   PyYAML error path.

Because the constructor is registered on the loader, nested mappings and
mappings inside sequences use it automatically. The registration is local to
the private subclass and does not mutate PyYAML's global `SafeLoader` behavior
for applications that also import `yaml`.

### Manager integration

`src/gpconfig/manager.py` will import `load_yaml` from the private module and
replace only this expression inside `_load_yaml_dict()`:

```python
raw_data = yaml.safe_load(f)
```

with:

```python
raw_data = load_yaml(f)
```

The surrounding `open(..., encoding="utf-8")`, `FileNotFoundError` handling,
`except yaml.YAMLError`, empty-document normalization, and top-level mapping
validation remain unchanged. The resulting data flow is:

```text
YAML file -> duplicate-aware SafeLoader -> dict -> root type check -> Pydantic
```

No public API changes are introduced. `global_env.yaml` receives the new
behavior during manager initialization because `_load_global_env()` already
delegates to `_load_yaml_dict()`.

## Duplicate-Key Semantics

Duplicate detection is scoped to one mapping node. The same resolved key may
appear in two separate mappings without error.

Keys are compared after SafeLoader resolution. Consequently, keys with different
source spelling but equal Python values are duplicates. Examples include:

```yaml
1: integer
true: boolean
```

and:

```yaml
null: first
~: second
```

YAML merge keys are excluded from the explicit-key snapshot. A legal explicit
override of a merged default remains valid:

```yaml
defaults: &defaults
  host: localhost
  port: 5432
service:
  <<: *defaults
  port: 6432
```

The loaded `service.port` remains `6432`. This fix does not reinterpret multiple
merge sources or duplicate merge-key syntax; it preserves PyYAML's current merge
behavior and rejects only duplicate explicit mapping keys.

## Error Contract

The private loader raises `yaml.constructor.ConstructorError`, a
`yaml.YAMLError` subclass. The error text includes a readable representation of
the duplicate key and labels the first and repeated locations. PyYAML source
marks are zero-based internally but render as 1-based line and column values.
When parsing an opened file object, the marks also include the file path.

The existing `_load_yaml_dict()` wrapper converts the YAML error to:

```text
ConfigValidationError
|-- original_error: ConstructorError
`-- __cause__: ConstructorError
```

`ConfigValidationError.path` remains the logical dotted path supplied by the
caller. The exact full message is not a stable API; callers may rely on the
exception types and the presence of the path, key, and source locations.

Files that previously relied on silent last-value-wins behavior will fail to
load. This is the intentional compatibility break for the bug fix, with no
opt-out.

## Test Design

Add regression coverage to `tests/test_yaml_loading.py` at the existing
`_load_yaml_dict()` and manager integration boundaries:

1. A duplicate top-level string key raises `ConfigValidationError`; its message
   contains the file path, key, first line/column, and repeated line/column.
2. The same test verifies `original_error` and `__cause__` are the same
   `yaml.YAMLError` instance.
3. A duplicate in a nested mapping is rejected.
4. A duplicate in a mapping inside a list is rejected.
5. A duplicate in `global_env.yaml` is rejected during manager initialization.
6. Unicode duplicate keys are rejected and the readable key appears in the
   message.
7. Resolved-equal textual variants such as `1`/`true` and `null`/`~` are
   rejected.
8. The same key in different mappings loads successfully.
9. A valid merge plus explicit override loads to the same dictionary produced
   by PyYAML 6.0.3 before the fix.

Existing tests already preserve the expected behavior for normal mappings,
empty and comments-only documents, top-level lists and scalars, malformed YAML,
and ordinary `get_config()` loading. The full suite ensures those cases remain
unchanged.

Verification commands must use the repository virtual environment:

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
```

## Documentation and Release

Update the English and Chinese documentation together:

- `docs/exceptions.md` and `docs/zh/exceptions.md`: add duplicate explicit YAML
  keys to `ConfigValidationError` trigger conditions and document the key,
  file, first location, repeated location, `original_error`, and exception-chain
  behavior.
- `docs/manager.md` and `docs/zh/manager.md`: extend `get_config()` failure
  documentation to include duplicate keys and their diagnostics.

`README.md` and `README.zh-CN.md` do not describe the YAML error contract and do
not require changes.

Create a `0.3.5` section dated 2026-08-02 in `CHANGELOG.md`, describing the
intentional rejection of duplicate explicit keys, retained safe loading and
merge behavior, diagnostic details, and documentation updates. Update changelog
comparison links for the new version.

Change the single version source in `src/gpconfig/__init__.py` from `0.3.4` to
`0.3.5`. `pyproject.toml` remains unchanged because Hatch reads the dynamic
version from that file.

The planned implementation commits are:

1. `fix: reject duplicate YAML mapping keys`
2. `docs: document duplicate YAML key validation`
3. `chore: bump version to 0.3.5`

## Acceptance Criteria

- Every mapping loaded through `_load_yaml_dict()` rejects duplicate explicit
  keys before ordinary dictionary construction.
- Detection covers arbitrary nesting, lists, ordinary configs, and
  `global_env.yaml`.
- Resolved-equal keys are rejected within the same mapping.
- The public error is `ConfigValidationError`, chained from a YAML error with
  actionable file, key, and first/repeated source locations.
- Legal merge behavior and all other existing valid YAML results are unchanged.
- No unsafe loader, global PyYAML mutation, public exception, or new dependency
  is introduced.
- English and Chinese docs, changelog, and version `0.3.5` are synchronized.
- The complete pytest suite and Ruff check pass.
