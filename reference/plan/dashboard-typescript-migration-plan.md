---
status: in-progress
updated: 2026-05-14
description: Implementation plan for migrating dashboard JavaScript to TypeScript with explicit stage gates and verification.
keywords:
  - dashboard
  - typescript
  - javascript
  - type safety
  - frontend build
  - stage gates
---

# Dashboard TypeScript migration plan

## Scope contract

P - Purpose: Produce a staged migration plan that moves the dashboard browser code from JavaScript to TypeScript without changing user-visible dashboard behavior.

A - Audience: The reader is a developer working in this repository who knows the Python package but may not know the dashboard asset pipeline.

U - Usage: This is a long-lived handoff plan that should guide implementation across multiple commits or pull requests.

S - Settings/Security: The dashboard must keep serving package-local assets only, and the migration must not add remote runtime dependencies or change API trust boundaries.

E - Exceptions: If the TypeScript build cannot emit stable browser-native ES modules, stop and revise the build approach. If backend payload shapes drift during migration, update the typed frontend contracts and backend tests in the same phase.

## Success criteria

S - Seek success: This task is done when the dashboard source is TypeScript, compiled JavaScript is served by FastAPI, and tests prove that source, build output, and API contracts stay aligned.

U - Uncover utility: The migration should reduce dashboard runtime errors caused by missing fields, unsafe DOM access, stale asset paths, and untyped API responses.

C - Choose criteria: Each phase must have a named gate, exact verification commands, and a rollback point.

C - Create checkpoints: Stop after each phase and do not start the next phase until its gate passes.

E - Expose evidence: Each phase must leave test output, changed file paths, and any contract decisions in the commit or pull request body.

S - Stay simple: Use plain TypeScript and browser-native ES modules first; do not add React, Vite, bundling, or schema generation in the initial migration.

S - Sustain scope: Do not redesign dashboard UI, CSS, API routes, Python metrics models, or live collection behavior unless a type contract exposes a real bug.

## Current state

- Dashboard JavaScript source lives in `src/token_machine/dashboard/assets/js/`.
- The browser entrypoint is `/assets/js/dashboard.js`.
- FastAPI serves package assets through `src/token_machine/dashboard/assets.py`.
- The dashboard template imports the entrypoint as a browser module.
- Existing tests assert that packaged JavaScript files are served and that dashboard assets do not use remote URLs.
- `package.json`, `pnpm-lock.yaml`, `tsconfig.json`, and `biome.json` provide the TypeScript build lane.
- TypeScript source now lives in `src/token_machine/dashboard/assets/ts/`.
- Generated JavaScript remains in `src/token_machine/dashboard/assets/js/`.

## Target state

- TypeScript source lives in `src/token_machine/dashboard/assets/ts/`.
- Generated JavaScript remains in `src/token_machine/dashboard/assets/js/`.
- The HTML template keeps importing `/assets/js/dashboard.js`.
- Python packaging keeps serving compiled JavaScript from the existing asset route.
- Frontend data contracts define the shapes returned by `/api/summary`, `/api/live`, and `/api/debug/reload`.
- CI or local verification fails when TypeScript source does not compile or when compiled assets are stale.

## Phase 0 - Baseline and inventory

### Implementation steps

1. Record the exact JavaScript module list under `src/token_machine/dashboard/assets/js/`.
2. Record which tests currently inspect dashboard JavaScript files.
3. Run the existing verification commands before any migration changes.
4. Save the command results in the implementation notes or pull request body.

### Gate 0

Gate 0 passes only when these commands pass before migration work starts:

```shell
uv run pytest
uv run ruff format --check
uv run ruff check
uv run ty check
```

If any command fails, fix or explicitly document the pre-existing failure before Phase 1.

### Rollback point

No files should need rollback in this phase. If baseline checks fail, stop before adding TypeScript tooling.

## Phase 1 - Add TypeScript build lane

### Implementation steps

1. Add `package.json` with scripts for `typecheck`, `build:dashboard`, and `check:dashboard`.
2. Add `tsconfig.json` configured for strict browser TypeScript and ES module output.
3. Set the TypeScript output directory to `src/token_machine/dashboard/assets/js/`.
4. Keep source files in `src/token_machine/dashboard/assets/ts/`.
5. Add a small placeholder TypeScript module only if needed to verify the build path.
6. Do not change the dashboard template in this phase.

### Recommended compiler settings

- Use `strict: true`.
- Use `noUncheckedIndexedAccess: true`.
- Use `exactOptionalPropertyTypes: true` if it does not create excessive noise.
- Use `module: ES2022` or a newer browser-native module target.
- Use `target: ES2022` or the lowest target needed by supported browsers.
- Use `lib: ["DOM", "ES2022"]`.

### Gate 1

Gate 1 passes only when these commands pass:

```shell
pnpm typecheck
pnpm build:dashboard
pnpm check:dashboard
uv run pytest tests/test_dashboard.py
```

Add or update a Python test that proves `/assets/js/dashboard.js` is still served with a JavaScript content type.

### Rollback point

If TypeScript tooling breaks Python packaging or asset serving, remove the new Node files and return to the pre-Phase 1 tree.

## Phase 2 - Compile-equivalent module migration

### Implementation steps

1. Move one JavaScript module at a time from `assets/js/*.js` to `assets/ts/*.ts`.
2. Keep emitted JavaScript filenames unchanged.
3. Keep all browser imports ending in `.js`.
4. Add explicit types only where the compiler requires them.
5. Avoid behavior cleanup unless the compiler exposes a real defect.
6. Build after each small group of modules.

### Suggested module order

1. `format.js`
2. `icons.js`
3. `sections.js`
4. `api.js`
5. `intro.js`
6. `charts.js`
7. `models.js`
8. `sessions.js`
9. `live.js`
10. `dashboard.js`

Start with utility modules because they have fewer dependencies. Finish with `dashboard.ts` because it connects the full surface.

### Gate 2

Gate 2 passes only when these commands pass:

```shell
pnpm typecheck
pnpm build:dashboard
uv run pytest tests/test_dashboard.py
uv run pytest
```

Also manually inspect the generated `src/token_machine/dashboard/assets/js/dashboard.js` and confirm it imports sibling modules with `.js` paths.

### Rollback point

Rollback is per module. If a migrated module introduces uncertain behavior, restore that module from JavaScript source and continue only after the cause is known.

## Phase 3 - Typed API contracts

### Implementation steps

1. Add `src/token_machine/dashboard/assets/ts/types.ts`.
2. Define TypeScript interfaces for `DashboardData`, `DashboardSummary`, `DailySummary`, `ModelProfile`, `SessionProfile`, `LiveData`, `LiveUsageSnapshot`, and `ReloadState`.
3. Type `fetchSummary`, `fetchLive`, and `fetchReloadState` to return those interfaces.
4. Type dictionary-shaped fields as `Record<string, number>` or `Record<string, string>` where the backend contract is stable.
5. Use `unknown` at API boundaries only if a runtime parser is added in the same phase.
6. Keep backend dataclasses as the source of truth for field names.

### Gate 3

Gate 3 passes only when these commands pass:

```shell
pnpm typecheck
pnpm build:dashboard
uv run pytest tests/test_dashboard.py tests/test_live.py tests/test_metrics.py
uv run pytest
```

Add a targeted test or fixture assertion that includes representative `/api/summary` and `/api/live` payload fields used by the frontend.

### Rollback point

If frontend types reveal an ambiguous backend shape, keep the Python payload unchanged and loosen only the affected TypeScript field. Do not reshape backend data in this phase unless a dashboard bug is confirmed.

## Phase 4 - DOM and runtime hardening

### Implementation steps

1. Add typed DOM helpers for required elements and optional elements.
2. Replace unsafe direct DOM writes with helpers that handle missing optional nodes.
3. Add local element interfaces for custom properties such as metric animation state.
4. Make `dataset` reads explicit and guard unknown chart mode values.
5. Ensure polling callbacks and abort errors are typed.
6. Keep visible dashboard behavior unchanged.

### Gate 4

Gate 4 passes only when these commands pass:

```shell
pnpm typecheck
pnpm build:dashboard
uv run pytest tests/test_dashboard.py
uv run pytest
```

Run the dashboard locally and confirm the page loads, summary polling runs, live polling runs, and chart toggles still respond.

Use this command to serve the app:

```shell
uv run token-machine serve
```

### Rollback point

If a DOM helper creates broad churn, revert the helper and keep the narrower type guards that were proven useful.

## Phase 5 - Stale build prevention

### Implementation steps

1. Add a check that fails when TypeScript source is newer than generated JavaScript or when build output differs.
2. Wire `pnpm check:dashboard` to run typecheck and a deterministic build check.
3. Update repository documentation with the TypeScript build commands.
4. Update tests that scan `assets/js/*.js` so they continue validating generated assets.

### Gate 5

Gate 5 passes only when these commands pass:

```shell
pnpm check:dashboard
uv run pytest
uv run ruff format --check
uv run ruff check
uv run ty check
```

The repository must be clean after running the full verification sequence. If generated files change, commit them with the TypeScript source changes.

### Rollback point

If stale-build detection is noisy, replace it with a simpler timestamp or checksum check. Do not leave the repository without any stale-build guard.

## Phase 6 - Optional generated contracts

This phase is optional and should be done only after the manual TypeScript migration is stable.

### Implementation steps

1. Decide whether backend models should expose JSON Schema.
2. If schema generation is useful, introduce it in Python first.
3. Generate TypeScript types from the backend schema.
4. Replace matching manual interfaces with generated interfaces.
5. Keep hand-written UI-only types separate from generated API types.

### Gate 6

Gate 6 passes only when these commands pass:

```shell
pnpm check:dashboard
uv run pytest tests/test_dashboard.py tests/test_live.py tests/test_metrics.py
uv run pytest
uv run ty check
```

Add a test that fails when generated contract files are stale.

### Rollback point

If generated contracts add more maintenance cost than value, keep the manual TypeScript interfaces and close this phase as intentionally deferred.

## Commit plan

Use separate commits for clear review gates:

1. `add dashboard typescript build` - completed by `4f09363 migrate dashboard scripts to typescript`
2. `migrate dashboard modules to typescript` - completed by `4f09363 migrate dashboard scripts to typescript`
3. `type dashboard api contracts` - in progress
4. `harden dashboard dom types`
5. `guard dashboard build output` - completed by `4f09363 migrate dashboard scripts to typescript`

Each commit should pass its phase gate before the next commit starts.

## Descoped work

- Do not add React, Vite, or a bundled app architecture.
- Do not redesign the dashboard visual system.
- Do not change dashboard API routes unless a verified contract bug requires it.
- Do not fetch runtime assets from remote URLs.
- Do not move CSS into TypeScript.

## Final verification

Run this full sequence before considering the migration complete:

```shell
pnpm check:dashboard
uv run pytest
uv run ruff format --check
uv run ruff check
uv run ty check
uv run token-machine serve
```

The final manual check must confirm:

- The dashboard loads at the local server URL.
- `/assets/js/dashboard.js` returns JavaScript.
- `/api/summary` returns JSON.
- `/api/live` returns JSON.
- The chart toggles work.
- The live panel renders without console errors.
- The browser does not request remote JavaScript, fonts, or icons.
