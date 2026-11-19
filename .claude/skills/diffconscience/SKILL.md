---
name: diffconscience
description: "Pre-handoff audit of an AI agent's own changes. This skill should be used when an agent (or a human) is about to finish a coding task and hand a diff/PR to review — BEFORE calling it done. Runs deterministic checks over git diff output for the patterns human reviewers catch in the first 30 seconds: debug artifacts left in (print/console.log/dbg!), commented-out code, TODO/FIXME added, secrets in changed lines, hardcoded localhost/IPs, scope drift outside the declared task, and public-API changes with no doc updates. Provides: diffconscience CLI (check a diff file or pipe git diff), a handoff checklist, and scoring thresholds for CI. Skip it for diffs with no changed lines, or pure formatting churn where only formatting changed."
---

# diffconscience — the pre-handoff audit

The last check before saying "done". Reviews are slower than agents;
make the first 30 seconds of every review count by never shipping the
patterns reviewers flag instantly.

## When to run

Run it on the final diff, immediately before commit/PR/handoff:

```bash
git diff main...HEAD > /tmp/change.diff
python3 scripts/diffconscience.py /tmp/change.diff
```

Or pipe directly: `git diff main...HEAD | python3 scripts/diffconscience.py`

With a declared scope (recommended — catches drift):

```bash
python3 scripts/diffconscience.py /tmp/change.diff --scope src/auth
```

CI gate: `--strict` exits 1 on ANY finding; default exits 1 on secrets only.

## What it catches

| ID | Severity | Pattern |
|---|---|---|
| DC-SEC | error | Secrets in added lines (api keys, AWS, GitHub/OpenAI tokens, passwords, bearer tokens, private keys) |
| DC-DEBUG | warn | `print`/`console.log`/`dbg!`/`println!`/`NSLog` left in changed code (skipped in test files) |
| DC-LOCALHOST | warn | Hardcoded `localhost`/`127.0.0.1`/private IPs in changed lines (non-test files) |
| DC-TODO | warn | TODO/FIXME/HACK/XXX introduced |
| DC-DEADCODE | warn | Commented-out code added |
| DC-SCOPE | warn | Files touched outside the `--scope` declared for the task |
| DC-DOCS | warn | Export/public-API lines added with no README/docs/CHANGELOG in the diff |

Only ADDED lines are audited — pre-existing debt stays visible in your
linter, not duplicated here.

## The handoff protocol

1. Finish the work.
2. Generate the diff; run diffconscience.
3. Fix every ERROR (secrets are never acceptable — rotate anything committed).
4. Fix or explicitly justify every WARN (say why in the PR description).
5. Re-run: zero errors, every remaining warning justified in writing.
6. Only then: commit, PR, handoff.

## Scoring for teams

- **CI gate**: `diffconscience diff.txt --strict` — block PRs with any finding.
- **Softer gate**: default mode (errors only) in CI + WARN review in PR template.
- **Trend**: run in CI on every PR and track findings-per-PR over time; a
  rising curve is the earliest signal an agent's config/skill has degraded.

## Extend

New reviewer-instant-catch patterns belong here. Add a pattern to the
tables in `scripts/diffconscience.py` (SECRET_PATTERNS / DEBUG_PATTERNS or
a new check), add a case to `tests/`, one-line PR.
