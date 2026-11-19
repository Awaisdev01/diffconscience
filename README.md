# 🧭 diffconscience

**The pre-handoff audit for AI agent changes.**

Agents finish work faster than humans review it. The gap between "agent
says done" and "actually done" is where every reviewer burns their first
30 seconds: leftover `console.log`s, TODOs, commented-out code, hardcoded
localhost, and — worst — secrets pasted straight into the diff.

`diffconscience` audits the agent's own diff **before** the handoff, so
reviews start at the interesting part.

```
$ git diff main...HEAD | diffconscience
diffconscience: 3 files changed — 1 errors, 3 warnings

[DC-SEC] ERROR src/auth/login.ts:11
  possible secret: api key, openai key
    const apiKey = "sk-proj...";
```

## Why it exists

- Linters check the *codebase*. Reviewers check the *changes*. diffconscience
  audits exactly the changed lines — pre-existing debt stays out of the way.
- The patterns are universal: every AI-assisted team's PRs contain the same
  first-glance findings.
- It's deterministic: no model calls, no cost, no false "looks good" from a
  rubber-stamp review. Exit codes make it a CI gate.

## Checks

| ID | Severity | Pattern |
|---|---|---|
| DC-SEC | **error** | Secrets in added lines (API keys, AWS, GitHub/OpenAI tokens, passwords, private keys) |
| DC-DEBUG | warn | Debug artifacts left in changed code (`print`, `console.log`, `dbg!`, `println!`, `NSLog`) |
| DC-LOCALHOST | warn | Hardcoded localhost / private IPs |
| DC-TODO | warn | TODO / FIXME / HACK introduced |
| DC-DEADCODE | warn | Commented-out code added |
| DC-SCOPE | warn | Files outside the declared task scope (`--scope src/auth`) |
| DC-DOCS | warn | Public-API changes with no README/docs/CHANGELOG touched |

## Install

```bash
git clone https://github.com/awaisdev5765/diffconscience.git ~/.claude/skills/diffconscience
```

Cross-agent skill format (Claude Code, Cursor, Codex, Windsurf, Antigravity).

## Usage

```bash
# Audit the current change set:
git diff main...HEAD | diffconscience

# With scope drift detection:
diffconscience diff.txt --scope src/auth,src/api

# CI gate (blocks on ANY finding):
diffconscience diff.txt --strict

# JSON for tooling:
diffconscience diff.txt --json
```

## The handoff protocol

1. Finish the work
2. `git diff main...HEAD | diffconscience`
3. Fix every ERROR — secrets are never acceptable
4. Fix or justify every WARN in the PR description
5. Re-run → clean → commit, PR, handoff

## Part of a pipeline

| Stage | Tool |
|---|---|
| Design | [nativetap](https://github.com/awaisdev5765/nativetap) — mobile design intelligence |
| Shell correctness | [bashproof](https://github.com/awaisdev5765/bashproof) — agent-proof quoting |
| **This diff** | **diffconscience — pre-handoff audit** |
| Code quality | [prism_doctor](https://pub.dev/packages/prism_doctor) — design-system lints |
| Launch | [shipcheck](https://pub.dev/packages/shipcheck) — release-readiness audit |
| AI features | [promptguard](https://pub.dev/packages/promptguard) — prompt regression tests |

## License

MIT — see [LICENSE](LICENSE).
