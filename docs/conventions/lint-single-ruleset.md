`ruff.toml` at the repo root is the **single source** for both the rule set and
the lint scope; `ruff check .` is the only command (CI, `verify-done.sh §3`, and
the `auto-format` hook all resolve to it). Two traps it exists to close:

- **No project config → ruff falls back to the developer's global
  `~/.config/ruff/ruff.toml`** (which this kit itself installs). That masked a
  real CI failure once: local green, CI red.
- **Ruff's *default* rule set changes between releases** (0.15 enables E402, 0.16
  does not), so relying on defaults makes two machines disagree. The rules are
  therefore listed explicitly, and the version is pinned in `.ruff-version`
  (CI installs exactly that; `verify-done.sh` warns when the local ruff differs).

Raising the ruff pin is a deliberate act: bump `.ruff-version`, fix what the new
version flags, land both together.

**The test runner is pinned the same way.** `.pytest-version` is the pin; CI
installs exactly it, and `verify-done.sh §4` warns when the local pytest differs.
pytest changes collection, fixture, and deprecation behavior across majors, so an
unpinned runner means CI silently floats to the newest release and can go red with
no code change — the same failure `.ruff-version` exists to prevent.

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install "pytest==$(cat .pytest-version)" "ruff==$(cat .ruff-version)"
```
