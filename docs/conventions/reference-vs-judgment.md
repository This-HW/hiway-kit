When a reference project (e.g. `obra/superpowers`) does something a particular way, that's
evidence of a working pattern — not evidence that this repo needs the same thing. Before porting
a tool or convention from a reference, check whether **this repo's own structure has the problem
the reference is solving.**

Concrete case (2026-08-27, W-022 R8): superpowers ships a stale-version-string audit
(`.version-bump.json`'s `audit.exclude`) because it hand-edits six manifest files on every
release — a real place for a version claim to go stale. This repo generates its target manifests
from a single SSOT and gates the generation (drift check), so the failure mode the audit exists to
catch doesn't occur here. The tool was built, run against the real repo (93 hits, mostly legitimate
incident retrospectives in code comments rather than stale claims), and removed once that became
clear — see `CHANGELOG.md`'s `[Unreleased]` entry and `git log` for the build-then-revert pair.

Copying the reference's answer without first checking whether the question applies is the mistake
this is here to prevent.
