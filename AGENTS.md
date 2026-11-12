# Repository Guidelines

## Project Structure & Module Organization

`app.py` is the Flask entry point and serves `templates/` and `static/`. Business automation lives under `src/`: `src/expedicao/` contains shipping and SAP flows; `src/estoque/` contains inventory transactions; and `src/utils/` provides shared helpers. Tests are in `tests/`; root-level `debug_*.py` and `test_auto_update.py` are diagnostic scripts. Packaging files include `app.spec`, `BUILD.bat`, and `Dockerfile`. Treat spreadsheets, screenshots, downloads, databases, and `dist/` as runtime or generated artifacts unless explicitly required.

## Build, Test, and Development Commands

- `python -m venv .venv` and `.\.venv\Scripts\Activate.ps1`: create and activate the Windows development environment.
- `python -m pip install -r requirements.txt`: install application dependencies.
- `python app.py`: run the local Flask UI at `http://127.0.0.1:5000`.
- `python -m pytest tests`: run the automated cabotage and Excel tests (install `pytest` separately if unavailable).
- `python test_auto_update.py`: run the interactive updater/configuration checks.
- `BUILD.bat`: create the PyInstaller distribution. The manual equivalent is `python -m PyInstaller app.spec`.
- `docker compose up --build`: build and start the containerized service defined in `compose.yaml`.

## Coding Style & Naming Conventions

Use Python with four-space indentation and PEP 8 spacing. Follow existing Portuguese domain vocabulary: modules and functions use `snake_case`, classes use `PascalCase`, and constants use `UPPER_SNAKE_CASE`. Keep Flask routes thin and place reusable workflow logic in `src/`. Prefer focused helper functions, explicit error logging through shared utilities, and comments only where SAP or spreadsheet behavior is not self-evident. No formatter or linter is currently configured; keep imports grouped and avoid unrelated reformatting.

## Testing Guidelines

Tests use pytest-style functions named `test_<behavior>`. Add tests under `tests/test_<feature>.py`, using in-memory Excel data and `unittest.mock` for external systems. Cover success cases, malformed spreadsheet values, filtering, and formatting regressions. Never require live SAP, SharePoint, or production credentials in automated tests.

## Commit & Pull Request Guidelines

Recent commits use short, imperative Portuguese summaries such as `Atualizando robo das ordens de frete`, with release commits prefixed by a version (for example, `v1.2.5 - ...`). Keep each commit scoped to one behavior. Pull requests should explain the affected workflow, verification commands, configuration changes, and linked issue. Include screenshots for UI changes and sanitized sample input/output for Excel changes.

## Security & Configuration

Keep `.env`, credentials, local databases, logs, and customer data untracked. Redact SAP document numbers and business data from screenshots and fixtures. Document new environment variables without committing their values.
