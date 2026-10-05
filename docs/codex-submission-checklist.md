---
status: current
as_of: 2026-10-05
---

# Codex Public Directory Submission Checklist

> **Current channel status lives in `docs/marketplace-submission.md`'s summary table** — this file
> keeps the OpenAI procedure and its record only.

> **This is a human action, not something an agent can execute.** Public submission
> requires an OpenAI/ChatGPT account with publisher permissions — the same kind of
> account-scoped action as pushing to `main` or creating a GitHub release. Nothing
> in this checklist should be run by an agent as a submission; it documents what a
> human needs to do and what this repo has already prepared for them.
>
> This is distinct from **local/marketplace installation**, which already works
> today without any submission — see the README's "Other Harnesses" section
> (`codex plugin marketplace add <repo>` → `codex plugin add
> hiway-kit@hiway-kit-marketplace`). Submission is only needed to be
> listed in the shared ChatGPT/Codex "universal directory" alongside OpenAI-curated
> plugins.

## Status — 2026-09-30: **5.2.0 submitted, In review**

On 2026-09-30 the portal's entry point changed from *Create plugin → With MCP / Skills only* to a single
**Upload plugin** (ZIP) flow, which accepts a skills-only plugin. The section below from 2026-09-28 is kept as
history — the "Skills only missing" blocker no longer applies.

| Version | Portal result (automated checks) | Fixed in |
| --- | --- | --- |
| 5.1.1 | Needs attention — `interface.longDescription` missing | 5.1.2 (`plugin_long_description_empty` now checked locally) |
| 5.1.2 | Needs attention — privacy policy URL missing; *"Plugins containing hooks cannot be submitted"* | privacy: `PRIVACY.md` + `interface.privacyPolicyURL` |
| 5.1.3-probe.1/.2 | probe drafts (not submitted): dropping only the hook declarations still failed; dropping the whole `hooks/` directory → *"No issues found"* | 5.2.0 — skill tools moved `hooks/` → `tools/`, ZIP omits `hooks/` (`docs/specs/2026-09-30-tools-dir/`) |
| **5.2.0** | **Metadata: No issues; all 15 skills "Checks passed"** → Submitted for review 2026-09-30 ~10:45 KST | — |

**Attestations ticked at submission (each checked against a fact, not assumed):** Terms and
[Plugin Guidelines](https://developers.openai.com/plugins/plugin-guidelines) compliance (skills-only requirements:
clear purpose, own MIT content, published privacy policy, verified developer, support contact, all skills scanned);
applicable laws; no money/crypto/investment transfers (none — local developer tool); rights to third-party content
and APIs (the plugin calls no API and ships only its own content); suitable for users under 18, no mature content;
does not target children under 13.

The portal now lists `hiway-kit · Not published · Version 5.2.0 · In review`. The 5.1.x and probe drafts remain in
the list as "Needs attention" / "Not submitted"; they were never submitted. **Next:** after approval, **Publish**,
then confirm the listing in the directory before writing an install path into README/CLAUDE.md.
The 5.2.0 under review was uploaded with the earlier GitHub-hosted `websiteURL`/`privacyPolicyURL`; from 5.2.2 the ZIP carries the
product-site URLs, so they reach the portal with the next upload (5.2.0 is left as submitted).
OpenAI confirmed receipt by email (2026-09-30 10:47 KST, "ChatGPT Plugin Submission Received" — review against the
app guidelines, outcome by email). Support case 15960350 got one more generic reply (07:10 KST, about ChatGPT
workspace Skills availability); the Upload plugin flow made it moot, so it was left to close on its own.
Community thread 1401299 confirmed the same from another organization (2026-09-30 04:26Z): the ZIP upload flow passes
the skill scan that kept failing in the old *With MCP* form, and a plugin created in the old form must keep its
package name (`app-<id>`) as the manifest `name` or the upload fails with `plugin_name_mismatch`. hiway-kit was created
through Upload plugin, so its package name is `hiway-kit`. Each later
release is a new ZIP upload with a higher `version`.

## (역사) Status — 2026-09-28 (identity verified; blocked by a platform-side outage of Skills only)

Submission portal: OpenAI Platform → **Plugins** (`platform.openai.com/plugins`), per
[Submit plugins](https://developers.openai.com/plugins/deploy/submission). Checked through the Aside
browser signed in as `thisyj.work@gmail.com`:

| Requirement | State |
| --- | --- |
| Organization / role | ThisHW Organization · **Owner** · Apps Management **Write** ✅ |
| Verified developer identity | **Individual: Verified** ✅ (2026-09-28) |
| Submission type | ❌ "Create plugin" offers only **With MCP** ("uses the same MCP URL for every user"). The **Skills only** path that [the Claude-plugin guide](https://developers.openai.com/plugins/guides/submit-claude-plugin) prescribes for plugins without an MCP server is **not shown** for this organization yet. hiway-kit has no MCP server, so With MCP does not apply. |

**With MCP cannot carry a skills-only kit — checked, not assumed.** Its form does have a Skills tab
(ZIP/folder upload), but the Submit tab lists hard blockers: *"MCP server URL is required"* and *"Test
case scenario is required"*, plus domain verification of the MCP host and a demo recording URL. Using it
would mean standing up and hosting an MCP server only to pass the form. Opening the form auto-creates an
"Untitled Plugin" draft; the two created while checking were deleted.

**Why Skills only is missing — a platform-side problem, not our setup** (researched 2026-09-28):

- The docs list no eligibility condition for Skills only; their only troubleshooting items (role with
  write access, same organization as the verified identity, identity selectable) are all met here.
- Other organizations report the identical symptom from **2026-09-26**, both individual- and
  business-verified: [thread 1400892](https://community.openai.com/t/skills-only-missing-from-create-plugin-verified-business-identity-available/1400892)
  (support confirmed the setup, escalated *"whether skills-only public submission is currently
  enabled"*, no workaround). The same day, **every new skill safety scan started failing** for those
  orgs ("Activity task failed", [thread 1401299](https://community.openai.com/t/skill-safety-scan-always-ends-in-error-activity-task-failed-for-every-skill-in-my-org-including-a-one-line-say-hello-skill/1401299)).
  So even a Skills only upload would currently stall at the scan.
- No OpenAI staff reply or fix date in either thread as of 2026-09-29 13:50 KST (1400892: 8 posts, the latest
  from another org that published a skills-only plugin on ~09-26 and then saw the option disappear; 1401299: 3 posts,
  none since 2026-09-27). No support reply to our 09:45 KST clarification by the same time. We filed our own support
  request (organization `org-dwKLm12IsiU3BkwZROoLdmuk`) so our org is part of the escalation —
  **case 15960350** (Sev 4, auto-acknowledged 2026-09-28 20:32 KST). On 2026-09-29 08:31 KST support asked for a
  screen recording and screenshots (the ticket closes after a day without a reply); sent 08:49 KST — a frame-by-frame
  recording of the browser tab (verification → Plugins → Create plugin menu showing only With MCP), three
  screenshots, and the note that the skill safety scan passes for all 15 skills.
  09:27 KST support replied with a generic answer about ChatGPT workspace custom apps and MCP connectors (not this
  issue); 09:45 KST replied clarifying it is the Plugins Directory portal and asking to route the case to the
  portal team (citing the other organization's escalation).

**OpenAI's own skill safety scan: all 15 skills pass (2026-09-29, v5.0.3).** The With MCP draft's Skills tab
accepts skill uploads and runs the real scan without submitting anything. A ZIP with the 15 skill folders at its
root (not the plugin ZIP — that one is silently ignored there) came back **Passed** for every skill, with no errors
or warnings. So the scan outage reported from 2026-09-26 no longer affects this organization; only the missing
Skills only entry remains. The throwaway draft was deleted. How to repeat:
`git archive HEAD plugins/common/skills | tar -x -C $T && (cd $T/plugins/common/skills && zip -r <uploads>/all-skills.zip .)`
→ Create plugin → With MCP → Continue → Skills → upload → read each skill's status → delete the draft.

**Package is pre-validated.** `scripts/build-codex-zip.py --check` builds the ZIP from tracked files and
checks every documented error code that can be judged locally (submission-errors page). Running it first
caught a real blocker — `interface.category: "Coding"` is not an accepted value — fixed in 4.0.4
(`Developer Tools`). It also drops the Antigravity root `plugin.json` from the ZIP (no `version`/`author`,
and the portal reads a root `plugin.json` as a manifest candidate with undocumented precedence).
Expected warnings only: `agents/` and hooks are not part of a skills-only listing.

**(역사 — 2026-09-30 Upload plugin 흐름으로 대체됨) Once Skills only appears:**

1. `scripts/build-codex-zip.py --out ~/.aside/u/0/uploads/hiway-kit-codex-<ver>.zip` (refuses a dirty
   plugin root, so the ZIP matches the pushed release).
2. Portal → **Create plugin → Skills only** → upload → read every validation message → listing (display
   name `hiway-kit`, short description `Coding agent discipline kit`, long description ≤ 4,000, category
   **Developer Tools**, icons `plugins/common/assets/icon.png`, Developer Identity = the verified
   individual; Plugin Author must match that verified legal name) → policy attestations → **Submit for Review**.
3. Watch the skill safety scan (up to 2 h), then publish after approval. Each later version is a new
   ZIP upload with a higher `version` (`plugin_version_unchanged` otherwise).

## Tracking to publication (who owns it, how to resume)

Submission itself is done (5.2.0, 2026-09-30). What remains is human, account-scoped work: after OpenAI
approves, **Publish** in the portal, confirm the listing by searching the directory, then update the summary
table in `docs/marketplace-submission.md` and the README install section. Every later release is a new ZIP
upload (`scripts/build-codex-zip.py --out …`) with a higher `version`. An agent session may *read* portal and
directory state to report it; it does not submit, upload, or publish.

## What this repo already has ready

Run these before submitting — both should already be green on `main`:

```bash
python3 scripts/build-targets.py --check   # generated manifest matches the SSOT
./scripts/verify-done.sh                   # full local gate (its §14 is the manifest drift check)
```

The generated `plugins/common/.codex-plugin/plugin.json` already carries the fields
Codex's own docs describe as required/expected for a plugin manifest
`[confirmed: developers.openai.com/codex/plugins/build, 2026-08-26]`:

| Field | Present | Source |
| --- | --- | --- |
| `name` | ✅ | SSOT (`plugins/common/.claude-plugin/plugin.json`) |
| `version` | ✅ | SSOT |
| `description` | ✅ | SSOT |
| `author` (name/email/url) | ✅ | SSOT, passed through (`packaging/targets.json` `passthroughFields`) |
| `homepage` | ✅ | SSOT, passed through |
| `interface.websiteURL` / `privacyPolicyURL` | ✅ | `packaging/targets.json` codex `interface` — the product site `https://hiway.thishw.com/` and `https://hiway.thishw.com/privacy/` (since 5.2.2; `supportURL` stays the GitHub issues page) |
| `repository` | ✅ | SSOT, passed through |
| `license` | ✅ | SSOT, passed through |
| `keywords` | ✅ | SSOT, passed through |
| `interface` (displayName/shortDescription/category/capabilities) | ✅ | `packaging/targets.json` `codex.interface` |
| `skills` | ✅ | `"./skills/"`, only if `skills/` exists (count: see `scripts/check_doc_counts.py` — not repeated here so it cannot go stale) |
| `hooks` | ✅ | `"./hooks/hooks-codex.json"` — `packaging/targets.json` codex `hooks`. Ships `session-start` (run with `--portable-only`) and `auto-format` only; Codex skips them silently until the user trusts them (README *Trusting Codex hooks*) |

Everything in this table is regenerated by `python3 scripts/build-targets.py --write
--only codex` if the SSOT changes — don't hand-edit the manifest.

## What's NOT included, and why (don't try to add these before submitting)

- Three hooks — deliberately **not** in `hooks-codex.json`. The list and each reason
  are owned by `packaging/targets.json` (codex `hooks._omitted`); summarized:
  - `protect-sensitive` — on codex 0.153.4 a `PreToolUse` block did not stop the command. **On
    codex 0.159.3 it does** (`exit 2` and `permissionDecision: "deny"` both block, with a no-hook
    positive control — 2026-10-05 감사 A 실측(codex 0.159.3), 기록 `packaging/targets.json`(W2 갱신
    예정)). Porting the hook (its payload is `Bash`/`apply_patch` with `tool_input.command`, not
    Claude's `Edit`/`Write`) is a separate decision (`D-Codex-hook` in
    `docs/specs/2026-10-05-audit-remediation/spec.md`), so it is still not shipped.
  - `session-check` — it checks Claude Code environment assumptions (global
    `~/.claude` setup, `.claude/agents` dual-load). In a Codex session those conditions
    are always true, so it would warn every session — noise that drowns the real
    warnings (`docs/conventions/warning-signal.md`).
  - `stop-validator` — `Stop` fires, but the hook's value is resuming the turn with
    `{"decision":"block"}` so the agent fixes what failed. Whether that resume contract
    holds on Codex is unmeasured; without resumption it would only run pytest every turn
    and discard the result.

  Codex (marketplace install) gets session-start injection and auto-format only. The
  earlier finding that Codex could not load this kit's hooks at all
  (`docs/specs/2026-08-26-multi-harness-packaging.md` S4) is superseded by the separate
  `hooks-codex.json` manifest above.
- **The directory ZIP has no hooks at all** — `scripts/build-codex-zip.py` drops `hooks/` and the
  manifest `hooks` field (the portal rejects plugins containing hooks). A consumer who installs
  from the OpenAI directory therefore gets **skills only and no rule injection**; they must run
  `/harness-export` to get the norms into `AGENTS.md` (2026-10-05 감사 A 실측, n=1). The README's
  Codex section shows the two install paths side by side.
- `agents`, `rules` — Codex's plugin manifest has no dedicated field for either
  (platform fact, not a gap to fill before submission).

## (역사) What a human needed to do before submission

Identity verification, portal access, and the submission itself were completed by the maintainer
(2026-09-28 ~ 09-30, recorded above). The 2026-08-26 version of this list — "locate the portal",
"authenticate", "criteria `[unresolved]`" — is superseded by that record.

## After submission

- Record the submission date, reviewing account, and outcome somewhere durable
  (this file, or a new CHANGELOG entry) so the next `/native-watch` or packaging
  change knows a public listing exists and needs to stay in sync.
- If the manifest changes after listing (e.g. a version bump), re-run
  `python3 scripts/build-targets.py --write --only codex` and follow whatever
  update process the portal documents — this repo has not verified what that is
  `[unresolved]`.
