# Repository Guidelines

## Project Structure & Module Organization
- `main.py` is the executable entrypoint; `pyproject.toml` holds package metadata
- Use `reference/personal/` for user-reference material
- Use `reference/lessons/` for durable notes and remembered nuances
- Use `reference/plan/` for task plans and handoff notes
- Create subdirectories under `reference/` when needed
- Place new code in the appropriate folder as those modules are introduced

## Build, Test, and Development Commands
- Use version as declared in `.python-version` and `pyproject.toml`.
  - `uv run python main.py`: run the current local entrypoint.
  - `uv run pytest`: run tests once a `tests/` suite exists.
  - `uv run ruff format`: formats the code.
  - `uv run ruff check --fix.`: lint the repository.
  - `uv run ty check`: run type checks.
- Use `uv` for adding, installing, and executing Python code
- If a tool exposes its own CLI, prefer that CLI through `uv run` when possible

## Coding Style & Naming Conventions
- Use 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes
- Write short docstrings only when behavior isn't obvious
- Avoid single-letter variable names; use explicit pairs like `key` and `value`
- Model structured data with `dataclass`, Pydantic models, or `TypedDict` instead of raw dictionaries
- Always ensure typesaftey for runtime validation and enhanced intellisense 
- Share constants and enums rather than duplicating literals
- Keep changes surgical and follow caution-first approach
- Use concise sections and sentence-case prose in Markdown docs
- Use repository-relative paths in documentation (e.g., `reference/ARCHITECTURE.md`)

## Documentation, Memory & Planning
- Always use front matter in reference documents so metadata is easy to load and search. Include at least `status`, `updated` (created/modified), `description`, and `keywords`
- Put user-requested reference material in `reference/personal/`, creating a focused subdirectory when helpful
- If asked to remember something, or if you discover a reusable nuance worth preserving, write it to `reference/lessons/` with a search-friendly filename.
- When creating tasks or a plan, record it in `reference/plan/` as a failsafe for interrupted sessions

## Verification Guidelines
- New behavior should include targeted tests when practical. Match test names to observable behavior, for example `test_rejects_missing_token`
- Run checks for every area touched by the change. For cross-cutting work, run every affected section and report any command that could not be run

## Commit & Pull Request Guidelines
- Prefer short, imperative commits such as `init`; continue using brief imperative subjects and expand detail in the body when needed
- Keep each commit scoped to one logical change
- Pull requests should contain a pithy paragraph of why the PR exists using plain english
- All PRs should include a clear summary with the functional/technical changes made and their impact on the codebase, features, or functions in a single concise sentence
- Note any architecture or design docs updated alongside code, list verification steps, and attach screenshots only when UI files are present

## Security & Configuration Tips
- Do not commit `.env` files, secrets, or user-specific reference material under ignored paths like `reference/personal/`
- Treat external connectors and assumptions in `reference/ARCHITECTURE.md` as design constraints when adding integrations
