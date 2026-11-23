# Project Structure Cleanup Implementation Plan

**Goal:** Reduce root-directory clutter without changing runtime behavior.

**Architecture:** Keep the current root-level Python application entrypoints intact. Move standalone tests into `tests/unit/` and `tests/manual/`, remove obsolete handoff artifacts, and update documentation and ignore rules to match the new layout.

**Tech Stack:** Python 3.12, uv, standalone `test_*.py` scripts, PowerShell on Windows.

---

## Tasks

1. Create `tests/unit/` and move offline `test_*.py` files into it.
2. Create `tests/manual/` and move real IM/OCR/window automation checks into it.
3. Add small test path helpers so tests can still import root-level modules when run as `uv run python tests/unit/<file>.py` or `uv run python tests/manual/<file>.py`.
4. Remove obsolete handoff files and old log-parsing tests.
5. Update `README.md` and `AGENTS.md` so commands and structure descriptions match the new layout.
6. Expand `.gitignore` for common local caches and temporary output.
7. Run representative offline tests through `uv`.
