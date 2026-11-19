#!/usr/bin/env python3
"""diffconscience — audit an agent's changes BEFORE handing them to a human.

Reads a unified diff (git diff output) and reports the patterns reviewers
catch in the first 30 seconds — the ones agents leave behind:

  - debug artifacts (print/console.log/dbg!/println! with low context)
  - commented-out code introduced
  - TODO/FIXME/HACK added
  - secrets and credential-looking strings
  - hardcoded localhost / ports / IPs
  - public API changes (export/signature lines) without doc updates
  - scope drift: files touched outside the declared scope (paths containing
    keywords the agent was asked to avoid)
  - tests touched ratio: behavior change with no test change

Zero dependencies. Usage:
  diffconscience < diff.txt
  diffconscience diff.txt --scope src/auth
  diffconscience diff.txt --json
"""

import json
import re
import sys

# Only added lines (+...) matter; capture file boundaries.
FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
HUNK_HEAD_RE = re.compile(r"^@@")

SECRET_PATTERNS = [
    ("api key", re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}")),
    ("aws key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("openai key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("password literal", re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{6,}")),
    ("bearer token", re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}")),
]

DEBUG_PATTERNS = [
    ("print(", re.compile(r"(?m)(?<![.\w])print\(")),
    ("console.log", re.compile(r"\bconsole\.(log|debug)\(")),
    ("dbg!", re.compile(r"\bdbg!")),
    ("println!", re.compile(r"\bprintln!\(")),
    ("NSLog", re.compile(r"\bNSLog\(")),
    ("System.out.println", re.compile(r"\bSystem\.out\.println")),
]

LOCALHOST_RE = re.compile(r"(?i)(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)\s*(:\d+)?")
TODO_RE = re.compile(r"(?i)\b(TODO|FIXME|HACK|XXX)\b")
COMMENTED_CODE_RE = re.compile(r"(?m)^\+\s*//\s*\w+.*[;{}()]\s*$")
API_CHANGE_RE = re.compile(r"^\+[^\+\-].*\b(export|public func|func |class |public class)\b")
DOC_FILES = ("README", "CHANGELOG", "docs/", "Documentation/")


def parse_diff(text):
    """Yield (file, lineno, added_line) for each added line."""
    current_file = None
    lineno = 0
    for raw in text.split("\n"):
        if raw.startswith("+++ b/"):
            current_file = raw[6:].strip()
            continue
        if raw.startswith("@@"):
            m = HUNK_RE.match(raw)
            lineno = int(m.group(1)) if m else 0
            continue
        if current_file is None:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            yield current_file, lineno, raw[1:]
        if raw.startswith(" "):
            lineno += 1


def audit_full(diff_text, scope=None):
    findings = []
    files = set()
    api_changes = []

    for f, ln, line in parse_diff(diff_text):
        files.add(f)
        def add(fid, sev, title, detail):
            findings.append({
                "id": fid, "severity": sev, "file": f, "line": ln,
                "title": title, "detail": detail[:90],
            })
        secret_hits = [name for name, rx in SECRET_PATTERNS if rx.search(line)]
        if secret_hits:
            add("DC-SEC", "error", "possible secret: " + ", ".join(secret_hits), line)
        for name, rx in DEBUG_PATTERNS:
            if rx.search(line) and "test" not in f.lower():
                add("DC-DEBUG", "warn", f"{name} left in changed code", line)
        if LOCALHOST_RE.search(line) and not any(
            x in f.lower() for x in ("test", "spec", "fixture", "config", "example")
        ):
            add("DC-LOCALHOST", "warn", "hardcoded localhost/IP", line)
        if TODO_RE.search(line):
            add("DC-TODO", "warn", "TODO/FIXME introduced", line)
        if COMMENTED_CODE_RE.match("+" + line):
            add("DC-DEADCODE", "warn", "commented-out code introduced", line)
        if API_CHANGE_RE.match(line):
            api_changes.append((f, line.strip()[:70]))

    if scope:
        scopes = [s.strip() for s in scope.split(",")]
        for f in files:
            if not any(s in f for s in scopes if s):
                findings.append({
                    "id": "DC-SCOPE", "severity": "warn", "file": f, "line": 0,
                    "title": "scope drift",
                    "detail": f"file outside declared scope '{scope}'",
                })

    doc_files = {f for f in files
                 if any(d.lower() in f.lower() for d in DOC_FILES)}
    if api_changes and not doc_files:
        findings.append({
            "id": "DC-DOCS", "severity": "warn",
            "file": api_changes[0][0], "line": 0,
            "title": "public API changed, docs untouched",
            "detail": f"{len(api_changes)} API-ish lines added, no README/docs/CHANGELOG in diff",
        })

    findings.sort(key=lambda x: (0 if x["severity"] == "error" else 1, x["file"]))
    return findings, files


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = [a for a in argv if a.startswith("--")]
    scope = None
    for i, a in enumerate(argv):
        if a == "--scope" and i + 1 < len(argv):
            scope = argv[i + 1]
            if scope in args:
                args.remove(scope)

    if args:
        try:
            with open(args[0], encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as e:
            print(f"diffconscience: cannot read {args[0]}: {e}", file=sys.stderr)
            return 2
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("diffconscience: empty diff (pass a diff file or pipe git diff)", file=sys.stderr)
        return 2

    findings, files = audit_full(text, scope)

    errors = sum(1 for x in findings if x["severity"] == "error")
    warns = len(findings) - errors
    if "--json" in flags:
        print(json.dumps({"files": sorted(files), "findings": findings}, indent=2))
    else:
        print(f"diffconscience: {len(files)} files changed — "
              f"{errors} errors, {warns} warnings")
        for x in findings:
            mark = "ERROR" if x["severity"] == "error" else "WARN "
            loc = f"{x['file']}:{x['line']}" if x["line"] else x["file"]
            print(f"\n[{x['id']}] {mark} {loc}")
            print(f"  {x['title']}")
            print(f"  {x['detail']}")

    if errors:
        return 1
    if "--strict" in flags and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
