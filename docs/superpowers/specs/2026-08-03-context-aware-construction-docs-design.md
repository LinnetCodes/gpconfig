# Context-Aware Construction User Documentation — Design

> **Status:** Approved design (brainstorming 2026-08-03). Next step: writing-plans.

## Goal

Add user-facing documentation for the context-aware object construction feature
shipped on branch `context-aware-object-construction-refactor`, so that users can
discover when to override `GPConfigurable.from_config()`, how to write one, what
the construction context carries, and the pitfalls (cycle responsibility, object
non-caching vs. config caching). Ship bilingual EN + ZH pages in sync.

## Background

The feature is implemented and reviewed (commits `76579ec`..`2073d18`) but the
published docs do not mention it:

- `docs/configurable.md` and `docs/zh/configurable.md` — no `from_config`,
  no `GPConfigurableContext`, no context semantics.
- `docs/manager.md` and `docs/zh/manager.md` — `get_object` documented without
  the hook dispatch or context.
- The only write-up today is `dev_docs/gpconfig-context-aware-object-construction-migration-guide.md`,
  which targets maintainers migrating duck-typed registrations or an existing
  same-named `from_config()`. It is under a gitignored directory, not in the
  mkdocs nav, and not framed as user guidance.

This design fills that gap without changing code, tests, the version number, or
the migration guide.

## Approved Decisions (from brainstorming)

1. **Placement: hybrid (no new nav page).** Add a new section to
   `configurable.md` (EN + ZH) carrying the full user guidance; add a short
   paragraph to `manager.md`'s `get_object` (EN + ZH) explaining it calls
   `from_config` once and cross-linking back to `configurable.md`. Do NOT create
   a new page or change `mkdocs.yml` nav.
2. **Depth: core-focused.** Cover the decision rule, signatures, context
   semantics, ONE concrete runnable cross-config example, and the pitfalls
   (cycle, caching). Exclude portfolio-domain recursion, topologies, and
   advanced scenarios.
3. **Example verification: run it at execution time.** The implementation plan
   includes a step that runs the new example code through the `.venv`
   interpreter as a throwaway script to confirm it executes and produces the
   documented output. This is a one-shot verification (CI does not run doctests,
   and no doctest CI is being added); only the docs are committed.

## Scope

### Files modified

- `docs/configurable.md` — new "Context-Aware Construction" section.
- `docs/zh/configurable.md` — mirror section in Simplified Chinese.
- `docs/manager.md` — short `from_config`-dispatch paragraph in the `get_object`
  area + cross-link.
- `docs/zh/manager.md` — ZH mirror of the `manager.md` change.

### Files NOT modified

- `mkdocs.yml` (nav unchanged — no new page).
- `src/gpconfig/**` (no code change).
- `tests/**` (no test change).
- `src/gpconfig/__init__.py` `__version__` (stays `0.3.4`; version bump and
  release notes remain a separate, later release effort).
- `dev_docs/gpconfig-context-aware-object-construction-migration-guide.md`
  (unchanged — distinct audience).
- README, `.github/workflows/**`.

### Out of scope

- Version bump, release notes, changelog.
- Adding doctest CI or any new test.
- Portfolio / domain recursion, cycle-detection reference implementations,
  cross-folder `GPConfigFolder.get_object` advanced scenarios.
- Any change to the `GPConfigurableContext`, `from_config`, or
  `ConfigurableConstructionError` API.

## New `configurable.md` Section — Content Blueprint

Insert the new section **between `## config Property` and `## Complete Example`**,
so it follows basic usage and precedes the multi-example walkthrough. Use the
existing page conventions: H2 section, prose + fenced code, Google-style tone,
parallel EN/ZH structure.

### 1. Intro + when to override `from_config`

One-paragraph decision rule:

- Standard `__init__(self, config)` subclasses → **do not override**. The default
  `GPConfigurable.from_config(config, *, context)` delegates to `cls(config)`,
  so existing subclasses keep working unchanged.
- Override `from_config` **only when** the object must reference other configs in
  the same config tree at construction time (the context is the only way to
  reach the manager).

### 2. The construction hook and context

- Import line: `from gpconfig import GPConfigurable, GPConfigurableContext`.
- Signature block (verbatim from the implemented API):

  ```python
  @classmethod
  def from_config(
      cls,
      config,
      *,
      context: GPConfigurableContext,
  ):
      return cls(config)  # default implementation
  ```

- `GPConfigurableContext` field semantics (frozen/slotted, two fields):
  - `manager` — the `GPConfigManager` that received this `get_object` request.
    Use it to load related configs from the same tree.
  - `path` — canonical dotted path of the source YAML file, with the `.yaml`
    suffix and the optional project-name prefix stripped. Example: both
    `services.api` and `myapp.services.api` yield `path == "services.api"`.

### 3. Runnable example — referencing another config

A complete, runnable `Worker` whose `from_config` pulls a related `database`
config via `context.manager.get_config(...)`. Include: `DatabaseConfig`,
`WorkerConfig`, `Worker` (with overridden `from_config`), the two YAML files,
registration, `get_object`, and an assertion/`print` showing the worker sees the
database host. The example must run under `.venv/Scripts/python.exe` at execution
time.

The example explicitly contrasts the two manager calls a hook can make:

| Call | Triggers `from_config`? | Recurses? | Cached? |
|------|:---:|:---:|:---:|
| `context.manager.get_config(path, Cfg)` | No | No | Yes (per file) |
| `context.manager.get_object(path)` | Yes | Yes | No (new instance each call) |

### 4. Important constraints

Tight list:

- The hook MUST return an instance of the registered configurable class (a
  subclass instance is allowed). Any other return value raises
  `ConfigurableConstructionError`.
- Exceptions raised by the hook (business errors AND `TypeError` from an
  incompatible signature) propagate unchanged. The manager never retries the
  legacy `cls(config)` constructor after a hook failure.
- `get_object` does NOT cache objects — each call returns a fresh instance.
  `get_config` DOES cache config data per file. Choose accordingly when a hook
  references the "same" thing from multiple places.
- **Cycle detection is the caller's responsibility.** The manager performs no
  cycle detection or depth limiting; a `get_object("a")` whose hook calls
  `get_object("b")` whose hook calls back `get_object("a")` will recurse without
  bound and overflow the stack.

### 5. Note inside the section

One sentence restating that the default hook preserves the standard-subclass
contract, so most users never touch `from_config`.

## `manager.md` `get_object` Addition — Content Blueprint

After the existing `get_object` explanation, add ONE short paragraph (EN; mirror
in ZH):

- `get_object` resolves the config, looks up the registered configurable class,
  builds a `GPConfigurableContext(manager=self, path=<canonical>)`, and invokes
  `configurable_cls.from_config(config, context=context)` **exactly once**.
- The return value is validated against the registered class; mismatches raise
  `ConfigurableConstructionError`.
- Cross-link to `configurable.md#context-aware-construction` (use the i18n-aware
  link target) for when and how to override the hook.

Keep it to a paragraph + one short code snippet at most. The full guidance lives
in `configurable.md`.

## Verification

The implementation plan will include:

1. **Run the new example** through `.venv/Scripts/python.exe` as a throwaway
   script: confirm it executes without error and that the printed/asserted
   values match what the docs claim (the worker reads the database host; the
   canonical-path and caching claims hold). The script is not committed — only
   the docs are.
2. **Full `pytest`** (`-m pytest`) green and **`ruff check .`** clean, to confirm
   the doc change did not perturb anything (it should not touch code/tests, but
   the run confirms scope).
3. **Bilingual parity check**: each EN section has a ZH counterpart with the
   same code blocks, signatures, table rows, and constraint bullets.
4. **Scope check**: `git diff --name-only` lists only the four doc files; docs
   nav, version, code, tests, and migration guide untouched.

## Risks / Notes

- **Doc-example drift:** the only durable guard against the example code and the
  real API diverging is this one-time execution check, since CI does not run
  doctests. The example should avoid anything fragile (e.g. exact exception
  message text) and stick to stable public API surface.
- **Section length:** the new `configurable.md` section is the largest on the
  page. The table + tight bullet style (matching the existing "Notes" density)
  keeps it scannable.
- **No version bump:** consistent with the prior implementation plan's stance
  that the version and release notes are a later, concentrated release effort.
