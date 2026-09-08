The completion gate (`verify-done.sh`) and the installer (`setup.sh`) *are* shell —
linting Python rigorously while leaving them unchecked means the code that decides
"done" is the code nobody checks. `scripts/lint-shell.sh` is the single command
(CI and `verify-done.sh §3b` both call it); it owns the target list and the
severity threshold, so neither side can drift. Targets are resolved from
`git ls-files` by extension **and** shebang, so extensionless scripts like
`plugins/common/setup/pre-commit` are covered and new scripts need no registration.
shellcheck is pinned in `.shellcheck-version` and CI verifies the release tarball's
sha256 — bump both together or the step fails loudly.

One deliberate asymmetry with ruff: a *missing* shellcheck is a yellow note locally,
not a red. CI (pinned version) is the authoritative verdict; the local run is fast
feedback. It never reports green when it could not check.
