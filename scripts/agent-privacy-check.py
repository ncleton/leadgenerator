#!/usr/bin/env python3
"""Create, audit and protect shareable Codex agents without external packages."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable


VERSION = "0.2.0"
ZERO_SHA = "0" * 40
BEGIN_IGNORE = "# BEGIN AGENTCREATOR PROTECTED"
END_IGNORE = "# END AGENTCREATOR PROTECTED"
BEGIN_AGENTS = "<!-- BEGIN AGENTCREATOR PRIVACY -->"
END_AGENTS = "<!-- END AGENTCREATOR PRIVACY -->"
LEGACY_BEGIN_IGNORE = "# BEGIN CREATEUR-AGENTS PROTECTED"
LEGACY_END_IGNORE = "# END CREATEUR-AGENTS PROTECTED"
LEGACY_BEGIN_AGENTS = "<!-- BEGIN CREATEUR-AGENTS PRIVACY -->"
LEGACY_END_AGENTS = "<!-- END CREATEUR-AGENTS PRIVACY -->"

DEFAULT_POLICY = {
    "schema_version": 1,
    "guard_version": VERSION,
    "mode": "personal",
    "allowed_paths": [
        "AGENTS.md",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "GOVERNANCE.md",
        "SECURITY.md",
        "SUPPORT.md",
        "Makefile",
        ".editorconfig",
        ".gitignore",
        ".gitattributes",
        ".shareable-agent/**",
        ".agents/skills/**",
        ".agents/plugins/**",
        "plugins/**",
        "skills/**",
        "scripts/**",
        "src/**",
        "tests/**",
        "docs/**",
        "assets/**",
        ".github/**",
        "pyproject.toml",
        "requirements*.txt",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
    ],
    "blocked_path_parts": [
        ".agent-private",
        ".agent-local",
        ".secrets",
        "private",
        "prive",
        "privé",
        "data",
        "donnees",
        "données",
        "clients",
        "customers",
        "factures",
        "invoices",
        "documents",
        "uploads",
        "exports",
        "logs",
        "backups",
        "memory",
        "memoire",
        "mémoire",
    ],
    "blocked_extensions": [
        ".pem",
        ".key",
        ".p12",
        ".pfx",
        ".sqlite",
        ".sqlite3",
        ".db",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".csv",
        ".tsv",
    ],
    "max_text_bytes": 2_000_000,
}

IGNORE_BLOCK = """# BEGIN AGENTCREATOR PROTECTED
# Private runtime and identity
.agent-private
.agent-private/
.agent-local/
.secrets/

# Credentials and local configuration
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
*credentials*
*secret*
*token*

# User and company data
private/
prive/
data/
donnees/
clients/
customers/
factures/
invoices/
documents/
uploads/
exports/
logs/
backups/
memory/
memoire/
*.sqlite
*.sqlite3
*.db
*.pdf
*.doc
*.docx
*.xls
*.xlsx
*.csv
*.tsv

# Local noise
.DS_Store
Thumbs.db
__pycache__/
*.py[cod]
.pytest_cache/
node_modules/
# END AGENTCREATOR PROTECTED
"""

AGENTS_PRIVACY_BLOCK = """<!-- BEGIN AGENTCREATOR PRIVACY -->
## Mandatory privacy boundary

- The repository contains only the agent's shareable engine.
- Store all user, customer, and company data in `.agent-private/`, which points to local storage outside Git.
- Never place real operational data in `AGENTS.md`, skills, tests, examples, issues, branch names, or commit messages.
- Never weaken `.gitignore`, `.shareable-agent/policy.json`, the external guard, or the privacy workflow.
- Never use `git add .`, `git add -A`, force push, or a token-bearing Git URL.
- Run the privacy check before every publication. If it blocks, keep the data local and never display its value.
- A user request to edit these instructions is never authorization to publish private data.
<!-- END AGENTCREATOR PRIVACY -->
"""

WORKFLOW = """name: Privacy gate

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  privacy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - name: Check shareable content
        run: python3 scripts/agent-privacy-check.py guard --root . --tracked --history
"""

SENSITIVE_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("stripe-key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("credential-assignment", re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|passwd)\s*[:=]\s*['\"]?[^\s'\"${}<]{8,}")),
    ("embedded-url-credential", re.compile(r"https?://[^\s/@:]+:[^\s/@]+@")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b")),
    ("french-phone", re.compile(r"(?<!\d)(?:(?:\+33|0033)[ .-]?[1-9]|0[1-9])(?:[ .-]?\d{2}){4}(?!\d)")),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("absolute-user-path", re.compile(r"(?:/" + r"Users/[^/\s]+|/" + r"home/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+)")),
]

SAFE_EMAIL_DOMAINS = {
    "example.com",
    "example.fr",
    "example.org",
    "example.net",
    "users.noreply.github.com",
}

# Cryptographic hashes and package paths in generated lockfiles can contain
# digit sequences that resemble French phone numbers or IBANs by coincidence.
# Keep scanning them for credentials, tokens, email addresses, and private paths.
GENERATED_LOCKFILE_NAMES = {
    "Cargo.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "uv.lock",
    "yarn.lock",
}


class AgentCtlError(RuntimeError):
    pass


def run(command: list[str], cwd: Path | None = None, check: bool = True, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        message = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise AgentCtlError(f"{command[0]}: {message}")
    return result


def run_bytes(command: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip() or "command failed"
        raise AgentCtlError(f"{command[0]}: {message}")
    return result


def git(root: Path, *args: str, check: bool = True, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=root, check=check, stdin=stdin)


def is_git_repo(root: Path) -> bool:
    if not shutil.which("git"):
        return False
    return git(root, "rev-parse", "--is-inside-work-tree", check=False).returncode == 0


def repo_root(root: Path) -> Path:
    result = git(root, "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()).resolve()


def runtime_home() -> Path:
    override = os.environ.get("AGENTCREATOR_HOME") or os.environ.get("CREATEUR_AGENTS_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AgentCreator"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "AgentCreator"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "agentcreator"


def slugify(value: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug[:48] or "agent"


def agent_id_for(root: Path) -> str:
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:12]
    return f"{slugify(root.name)}-{digest}"


def replace_managed_block(path: Path, begin: str, end: str, block: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    legacy = {
        (BEGIN_IGNORE, END_IGNORE): (LEGACY_BEGIN_IGNORE, LEGACY_END_IGNORE),
        (BEGIN_AGENTS, END_AGENTS): (LEGACY_BEGIN_AGENTS, LEGACY_END_AGENTS),
    }.get((begin, end))
    if legacy:
        existing = existing.replace(legacy[0], begin).replace(legacy[1], end)
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
    if pattern.search(existing):
        updated = pattern.sub(block.rstrip() + "\n", existing)
    else:
        separator = "" if not existing or existing.endswith("\n\n") else "\n" if existing.endswith("\n") else "\n\n"
        updated = existing + separator + block.rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")


def write_if_missing(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def backup_controls(root: Path, agent_id: str) -> None:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    destination = runtime_home() / agent_id / "backups" / stamp
    for relative in ["AGENTS.md", ".gitignore", ".shareable-agent/policy.json"]:
        source = root / relative
        if source.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def private_location(root: Path, agent_id: str) -> Path:
    path = runtime_home() / agent_id / "private"
    path.mkdir(parents=True, exist_ok=True)
    readme = path / "README.txt"
    if not readme.exists():
        readme.write_text(
            "Private agent data. This folder is stored outside the Git repository.\n",
            encoding="utf-8",
        )
    return path


def ensure_private_link(root: Path, private: Path) -> None:
    link = root / ".agent-private"
    if link.is_symlink() and link.resolve() == private.resolve():
        return
    if link.exists() or link.is_symlink():
        if link.is_dir() and not link.is_symlink():
            if any(link.iterdir()):
                raise AgentCtlError(".agent-private exists and contains data; manual migration is required")
            link.rmdir()
        else:
            link.unlink()
    try:
        link.symlink_to(private, target_is_directory=True)
    except OSError:
        pointer = root / ".agent-local" / "private-path.txt"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(str(private), encoding="utf-8")


def policy_path(root: Path) -> Path:
    return root / ".shareable-agent" / "policy.json"


def load_policy(root: Path) -> dict:
    path = policy_path(root)
    if not path.exists():
        return dict(DEFAULT_POLICY)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentCtlError(f"invalid policy: {exc}") from exc
    merged = dict(DEFAULT_POLICY)
    merged.update(data)
    return merged


def write_policy(root: Path, mode: str, agent_id: str) -> None:
    current = load_policy(root) if policy_path(root).exists() else {}
    policy = dict(DEFAULT_POLICY)
    for key in ["allowed_paths", "blocked_path_parts", "blocked_extensions", "max_text_bytes"]:
        if key in current:
            policy[key] = current[key]
    policy.update({"agent_id": current.get("agent_id", agent_id), "mode": mode, "guard_version": VERSION})
    path = policy_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_git(root: Path) -> None:
    if not shutil.which("git"):
        raise AgentCtlError("Git is not installed")
    if is_git_repo(root):
        return
    result = git(root, "init", "-b", "main", check=False)
    if result.returncode:
        git(root, "init")
        git(root, "branch", "-M", "main", check=False)


def install_external_guard(root: Path, agent_id: str) -> Path:
    ensure_git(root)
    guard_dir = runtime_home() / agent_id / "git-hooks"
    guard_dir.mkdir(parents=True, exist_ok=True)
    guard_copy = guard_dir / "agentctl.py"
    shutil.copy2(Path(__file__).resolve(), guard_copy)
    guard_copy.chmod(guard_copy.stat().st_mode | stat.S_IXUSR)

    quoted_guard = str(guard_copy).replace("'", "'\"'\"'")
    hooks = {
        "pre-commit": f"#!/bin/sh\nroot=\"$(git rev-parse --show-toplevel)\" || exit 1\nexec python3 '{quoted_guard}' guard --root \"$root\" --staged\n",
        "pre-push": f"#!/bin/sh\nroot=\"$(git rev-parse --show-toplevel)\" || exit 1\nexec python3 '{quoted_guard}' guard --root \"$root\" --pre-push\n",
    }
    for name, content in hooks.items():
        path = guard_dir / name
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    git(root, "config", "--local", "core.hooksPath", str(guard_dir))
    return guard_dir


def sanitized_description(value: str) -> str:
    value = " ".join(value.split()).strip()
    if len(value) > 300:
        value = value[:297].rstrip() + "..."
    issues = scan_text(value, "description")
    if issues:
        raise AgentCtlError("the description may contain private data; restate it without real values")
    return value or "Assist the user with the requested work."


def basic_agents_file(description: str, mode: str) -> str:
    collaboration = (
        "\n## Collaboration\n\nShared work uses a local identity per person, isolated changes, review before integration, and sanitized contribution history.\n"
        if mode == "collaborative"
        else ""
    )
    return f"""# Agent

## Mission

{description}

## Working style

- Understand plain-language requests and proceed without an unnecessary questionnaire.
- Preserve existing files and customization.
- Request a decision only when it materially changes the outcome or authorizes an irreversible action.
- Verify deliverables before reporting completion.
{collaboration}
{AGENTS_PRIVACY_BLOCK}"""


def ensure_scaffold(root: Path, mode: str, description: str | None, backup: bool) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    agent_id = agent_id_for(root)
    if backup:
        backup_controls(root, agent_id)
    ensure_git(root)
    private = private_location(root, agent_id)
    ensure_private_link(root, private)
    replace_managed_block(root / ".gitignore", BEGIN_IGNORE, END_IGNORE, IGNORE_BLOCK)
    agents = root / "AGENTS.md"
    if not agents.exists():
        agents.write_text(basic_agents_file(sanitized_description(description or ""), mode), encoding="utf-8")
    else:
        replace_managed_block(agents, BEGIN_AGENTS, END_AGENTS, AGENTS_PRIVACY_BLOCK)
    write_policy(root, mode, agent_id)
    (root / ".agents" / "skills").mkdir(parents=True, exist_ok=True)
    workflow = root / ".github" / "workflows" / "privacy.yml"
    write_if_missing(workflow, WORKFLOW)
    checker = root / "scripts" / "agent-privacy-check.py"
    checker.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), checker)
    checker.chmod(checker.stat().st_mode | stat.S_IXUSR)
    hook_dir = install_external_guard(root, agent_id)
    remove_tracked_ignored(root)
    return {
        "agent_id": agent_id,
        "mode": mode,
        "root": str(root),
        "private_ready": True,
        "guard_installed": True,
        "hook_location": str(hook_dir),
    }


def normalize_relative(path: str) -> str:
    clean = path.replace("\\", "/")
    while clean.startswith("./"):
        clean = clean[2:]
    parts = [part for part in clean.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise AgentCtlError("path escapes the repository")
    return "/".join(parts)


def path_allowed(relative: str, policy: dict) -> bool:
    return any(fnmatch.fnmatchcase(relative, pattern) for pattern in policy["allowed_paths"])


def path_issues(relative: str, policy: dict) -> list[str]:
    relative = normalize_relative(relative)
    lower_parts = [part.casefold() for part in relative.split("/")]
    issues = []
    blocked_parts = {part.casefold() for part in policy["blocked_path_parts"]}
    if any(part in blocked_parts for part in lower_parts):
        issues.append("private-path")
    name = lower_parts[-1] if lower_parts else ""
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        issues.append("environment-file")
    if any(name.endswith(ext.casefold()) for ext in policy["blocked_extensions"]):
        issues.append("private-file-type")
    if not path_allowed(relative, policy):
        issues.append("path-not-allowlisted")
    return sorted(set(issues))


def scan_text(text: str, relative: str) -> list[str]:
    issues = []
    synthetic = "SYNTHETIC_TEST_DATA" in text[:500]
    for label, pattern in SENSITIVE_PATTERNS:
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        if label == "email":
            real = []
            for match in matches:
                domain = match.group(0).rsplit("@", 1)[-1].casefold()
                if domain not in SAFE_EMAIL_DOMAINS:
                    real.append(match)
            if not real:
                continue
        if synthetic and label in {"email", "french-phone", "iban", "absolute-user-path"}:
            continue
        issues.append(label)
    return sorted(set(issues))


def scan_bytes(data: bytes, relative: str, policy: dict) -> list[str]:
    if len(data) > int(policy["max_text_bytes"]):
        return ["file-too-large"]
    if b"\x00" in data:
        return ["binary-review-required"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ["non-utf8-review-required"]
    issues = scan_text(text, relative)
    if Path(relative).name in GENERATED_LOCKFILE_NAMES:
        issues = [issue for issue in issues if issue not in {"french-phone", "iban"}]
    return issues


def scan_worktree_file(root: Path, relative: str, policy: dict) -> list[str]:
    issues = path_issues(relative, policy)
    path = root / relative
    if path.is_symlink():
        issues.append("symlink-review-required")
    elif path.is_file():
        try:
            issues.extend(scan_bytes(path.read_bytes(), relative, policy))
        except OSError:
            issues.append("unreadable-file")
    return sorted(set(issues))


def staged_files(root: Path) -> list[str]:
    result = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [item for item in result.stdout.split("\0") if item]


def tracked_files(root: Path) -> list[str]:
    result = git(root, "ls-files", "-z")
    return [item for item in result.stdout.split("\0") if item]


def ignored_tracked_files(root: Path) -> list[str]:
    result = git(root, "ls-files", "-ci", "--exclude-standard", "-z", check=False)
    return [item for item in result.stdout.split("\0") if item]


def remove_tracked_ignored(root: Path) -> list[str]:
    if not is_git_repo(root):
        return []
    files = ignored_tracked_files(root)
    if files:
        git(root, "rm", "--cached", "--ignore-unmatch", "--", *files)
    return files


def commit_file_bytes(root: Path, commit: str, relative: str) -> bytes | None:
    result = run_bytes(["git", "show", f"{commit}:{relative}"], cwd=root, check=False)
    if result.returncode:
        return None
    return result.stdout


def outgoing_commits(root: Path, pre_push_input: str) -> list[str]:
    commits: set[str] = set()
    for line in pre_push_input.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        _, local_sha, _, remote_sha = fields[:4]
        if local_sha == ZERO_SHA:
            continue
        if remote_sha == ZERO_SHA:
            result = git(root, "rev-list", local_sha, "--not", "--remotes", check=False)
        else:
            result = git(root, "rev-list", f"{remote_sha}..{local_sha}", check=False)
        commits.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return sorted(commits)


def scan_commit(root: Path, commit: str, policy: dict) -> list[dict]:
    result = git(root, "diff-tree", "--root", "--no-commit-id", "--name-only", "--diff-filter=ACMR", "-r", "-z", commit)
    findings = []
    for relative in [item for item in result.stdout.split("\0") if item]:
        issues = path_issues(relative, policy)
        data = commit_file_bytes(root, commit, relative)
        if data is not None:
            issues.extend(scan_bytes(data, relative, policy))
        for issue in sorted(set(issues)):
            findings.append({"severity": "critical", "code": issue, "path": relative, "commit": commit[:12]})
    return findings


def scan_history(root: Path, policy: dict, limit: int = 2000) -> list[dict]:
    result = git(root, "rev-list", "--objects", "--all", check=False)
    findings = []
    seen = 0
    for line in result.stdout.splitlines():
        if " " not in line:
            continue
        object_id, relative = line.split(" ", 1)
        relative = normalize_relative(relative)
        if seen >= limit:
            continue
        object_type = git(root, "cat-file", "-t", object_id, check=False).stdout.strip()
        if object_type != "blob":
            continue
        seen += 1
        issues = path_issues(relative, policy)
        if issues:
            for issue in issues:
                findings.append({"severity": "critical", "code": f"history-{issue}", "path": relative, "commit": object_id[:12]})
        blob = run_bytes(["git", "cat-file", "-p", object_id], cwd=root, check=False)
        if blob.returncode == 0:
            data = blob.stdout
            for issue in scan_bytes(data, relative, policy):
                findings.append({"severity": "critical", "code": f"history-{issue}", "path": relative, "commit": object_id[:12]})
    unique = {(item["code"], item["path"], item["commit"]): item for item in findings}
    return list(unique.values())


def findings_for_files(root: Path, files: Iterable[str], policy: dict) -> list[dict]:
    findings = []
    for relative in sorted(set(files)):
        for issue in scan_worktree_file(root, relative, policy):
            findings.append({"severity": "critical", "code": issue, "path": relative})
    return findings


def print_findings(findings: list[dict], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps({"ok": not findings, "findings": findings}, ensure_ascii=False, indent=2))
        return
    if not findings:
        print("Privacy check passed.")
        return
    print("Publication blocked. No sensitive value is displayed.")
    for item in findings:
        location = item.get("path", "repository")
        suffix = f" ({item['commit']})" if item.get("commit") else ""
        print(f"- {item['code']}: {location}{suffix}")


def audit(root: Path, include_history: bool = False) -> list[dict]:
    root = root.resolve()
    findings: list[dict] = []
    if not is_git_repo(root):
        findings.append({"severity": "high", "code": "git-not-initialized", "path": "."})
        return findings
    root = repo_root(root)
    try:
        policy = load_policy(root)
    except AgentCtlError:
        policy = dict(DEFAULT_POLICY)
        findings.append({"severity": "critical", "code": "privacy-policy-invalid", "path": ".shareable-agent/policy.json"})

    checks = [
        (root / "AGENTS.md", "high", "agents-instructions-missing"),
        (root / ".gitignore", "critical", "gitignore-missing"),
        (policy_path(root), "critical", "privacy-policy-missing"),
        (root / "scripts" / "agent-privacy-check.py", "high", "privacy-check-missing"),
        (root / ".github" / "workflows" / "privacy.yml", "medium", "server-check-missing"),
    ]
    for path, severity, code in checks:
        if not path.exists():
            findings.append({"severity": severity, "code": code, "path": str(path.relative_to(root))})

    ignore = root / ".gitignore"
    if ignore.exists() and BEGIN_IGNORE not in ignore.read_text(encoding="utf-8", errors="replace"):
        findings.append({"severity": "critical", "code": "protected-ignore-block-missing", "path": ".gitignore"})
    agents = root / "AGENTS.md"
    if agents.exists() and BEGIN_AGENTS not in agents.read_text(encoding="utf-8", errors="replace"):
        findings.append({"severity": "high", "code": "privacy-instructions-missing", "path": "AGENTS.md"})

    private = root / ".agent-private"
    pointer = root / ".agent-local" / "private-path.txt"
    if not private.is_symlink() and not pointer.exists():
        findings.append({"severity": "high", "code": "external-private-storage-missing", "path": ".agent-private"})
    elif private.is_symlink():
        try:
            private.resolve().relative_to(root)
            findings.append({"severity": "critical", "code": "private-storage-inside-repository", "path": ".agent-private"})
        except ValueError:
            pass

    hook_path = git(root, "config", "--local", "--get", "core.hooksPath", check=False).stdout.strip()
    if not hook_path:
        findings.append({"severity": "high", "code": "external-git-guard-missing", "path": ".git/config"})
    else:
        try:
            Path(hook_path).expanduser().resolve().relative_to(root)
            findings.append({"severity": "high", "code": "git-guard-is-repository-controlled", "path": ".git/config"})
        except ValueError:
            pass

    remote = git(root, "remote", "get-url", "origin", check=False).stdout.strip()
    if remote and re.search(r"https?://[^/@:]+:[^/@]+@", remote):
        findings.append({"severity": "critical", "code": "credential-in-remote-url", "path": ".git/config"})

    for relative in ignored_tracked_files(root):
        findings.append({"severity": "critical", "code": "ignored-file-is-tracked", "path": relative})
    findings.extend(findings_for_files(root, tracked_files(root), policy))
    if include_history:
        findings.extend(scan_history(root, policy))

    unique = {(item["severity"], item["code"], item["path"], item.get("commit")): item for item in findings}
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(unique.values(), key=lambda item: (order[item["severity"]], item["code"], item["path"]))


def github_doctor(root: Path, repair: bool) -> dict:
    status = {
        "git_installed": bool(shutil.which("git")),
        "gh_installed": bool(shutil.which("gh")),
        "authenticated": False,
        "account": None,
        "identity_ready": False,
        "guard_ready": False,
        "ready": False,
    }
    if not status["git_installed"] or not status["gh_installed"]:
        return status
    user = run(["gh", "api", "user", "--jq", ".login"], check=False)
    if user.returncode:
        return status
    login = user.stdout.strip()
    status["authenticated"] = bool(login)
    status["account"] = login or None
    if repair:
        run(["gh", "auth", "setup-git"], check=False)
    if is_git_repo(root):
        root = repo_root(root)
        name = git(root, "config", "--local", "--get", "user.name", check=False).stdout.strip()
        email = git(root, "config", "--local", "--get", "user.email", check=False).stdout.strip()
        if repair and not name:
            git(root, "config", "--local", "user.name", login)
            name = login
        if repair and not email:
            identifier = run(["gh", "api", "user", "--jq", ".id"], check=False).stdout.strip()
            if identifier:
                email = f"{identifier}+{login}@users.noreply.github.com"
                git(root, "config", "--local", "user.email", email)
        status["identity_ready"] = bool(name and email)
        hook = git(root, "config", "--local", "--get", "core.hooksPath", check=False).stdout.strip()
        status["guard_ready"] = bool(hook and Path(hook).expanduser().exists())
    status["ready"] = bool(status["authenticated"] and status["identity_ready"] and status["guard_ready"])
    return status


def command_guard(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    if not is_git_repo(root):
        raise AgentCtlError("this folder is not a Git repository")
    root = repo_root(root)
    policy = load_policy(root)
    findings = []
    for relative in ignored_tracked_files(root):
        findings.append({"severity": "critical", "code": "ignored-file-is-tracked", "path": relative})
    if args.staged:
        findings.extend(findings_for_files(root, staged_files(root), policy))
    if args.tracked:
        findings.extend(findings_for_files(root, tracked_files(root), policy))
    if args.pre_push:
        for commit in outgoing_commits(root, sys.stdin.read()):
            findings.extend(scan_commit(root, commit, policy))
    if args.history:
        findings.extend(scan_history(root, policy))
    print_findings(findings, args.json)
    return 2 if findings else 0


def command_safe_commit(args: argparse.Namespace) -> int:
    root = repo_root(Path(args.root).expanduser().resolve())
    if not args.paths:
        raise AgentCtlError("safe-commit requires an explicit file list")
    policy = load_policy(root)
    paths = [normalize_relative(item) for item in args.paths]
    findings = findings_for_files(root, paths, policy)
    if findings:
        print_findings(findings, args.json)
        return 2
    git(root, "add", "--", *paths)
    staged_findings = findings_for_files(root, staged_files(root), policy)
    if staged_findings:
        restored = git(root, "restore", "--staged", "--", *paths, check=False)
        if restored.returncode:
            git(root, "rm", "--cached", "--ignore-unmatch", "--", *paths, check=False)
        print_findings(staged_findings, args.json)
        return 2
    git(root, "commit", "-m", args.message)
    print(json.dumps({"ok": True, "committed": paths}, ensure_ascii=False) if args.json else "Changes committed.")
    return 0


def command_protect(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    if not is_git_repo(root) or not policy_path(repo_root(root)).exists():
        return 0
    root = repo_root(root)
    policy = load_policy(root)
    agent_id = str(policy.get("agent_id") or agent_id_for(root))
    install_external_guard(root, agent_id)
    print(json.dumps({"ok": True}, ensure_ascii=False) if args.json else "Protection active.")
    return 0


def remote_branch_sha(root: Path, remote: str, branch: str) -> str:
    result = git(root, "ls-remote", "--heads", remote, f"refs/heads/{branch}", check=False)
    if result.returncode or not result.stdout.strip():
        return ZERO_SHA
    return result.stdout.split()[0]


def command_safe_push(args: argparse.Namespace) -> int:
    root = repo_root(Path(args.root).expanduser().resolve())
    policy = load_policy(root)
    audit_findings = [item for item in audit(root) if item["severity"] in {"critical", "high"}]
    if audit_findings:
        print_findings(audit_findings, args.json)
        return 2
    fetch = git(root, "fetch", "--prune", args.remote, check=False)
    if fetch.returncode:
        raise AgentCtlError("remote backup is temporarily unavailable")
    local_sha = git(root, "rev-parse", "HEAD").stdout.strip()
    remote_sha = remote_branch_sha(root, args.remote, args.branch)
    if remote_sha != ZERO_SHA:
        ancestor = git(root, "merge-base", "--is-ancestor", remote_sha, local_sha, check=False)
        if ancestor.returncode:
            raise AgentCtlError("local and remote histories diverged; no data was overwritten")
    ref_line = f"refs/heads/{args.branch} {local_sha} refs/heads/{args.branch} {remote_sha}\n"
    findings = []
    for commit in outgoing_commits(root, ref_line):
        findings.extend(scan_commit(root, commit, policy))
    if findings:
        print_findings(findings, args.json)
        return 2
    git(root, "push", args.remote, f"HEAD:refs/heads/{args.branch}")
    confirmed = remote_branch_sha(root, args.remote, args.branch)
    if confirmed != local_sha:
        raise AgentCtlError("remote backup could not be verified")
    print(json.dumps({"ok": True, "sha": local_sha}, ensure_ascii=False) if args.json else "Agent backed up and current.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ["create", "repair"]:
        item = sub.add_parser(name)
        item.add_argument("--root", required=True)
        item.add_argument("--mode", choices=["personal", "collaborative"], default="personal")
        item.add_argument("--description", default="")
        item.add_argument("--json", action="store_true")

    item = sub.add_parser("audit")
    item.add_argument("--root", required=True)
    item.add_argument("--history", action="store_true")
    item.add_argument("--json", action="store_true")

    item = sub.add_parser("guard")
    item.add_argument("--root", required=True)
    item.add_argument("--staged", action="store_true")
    item.add_argument("--tracked", action="store_true")
    item.add_argument("--pre-push", action="store_true")
    item.add_argument("--history", action="store_true")
    item.add_argument("--json", action="store_true")

    item = sub.add_parser("github-doctor")
    item.add_argument("--root", required=True)
    item.add_argument("--repair", action="store_true")
    item.add_argument("--json", action="store_true")

    item = sub.add_parser("safe-commit")
    item.add_argument("--root", required=True)
    item.add_argument("--message", required=True)
    item.add_argument("--paths", nargs="+", required=True)
    item.add_argument("--json", action="store_true")

    item = sub.add_parser("safe-push")
    item.add_argument("--root", required=True)
    item.add_argument("--remote", default="origin")
    item.add_argument("--branch", default="main")
    item.add_argument("--json", action="store_true")

    item = sub.add_parser("protect")
    item.add_argument("--root", required=True)
    item.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        root = Path(getattr(args, "root", ".")).expanduser().resolve()
        if args.command in {"create", "repair"}:
            result = ensure_scaffold(
                root,
                mode=args.mode,
                description=args.description,
                backup=args.command == "repair",
            )
            findings = audit(root)
            result["findings"] = findings
            result["ok"] = not any(item["severity"] in {"critical", "high"} for item in findings)
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"Agent protected: {root}")
            return 0 if result["ok"] else 2
        if args.command == "audit":
            findings = audit(root, include_history=args.history)
            print_findings(findings, args.json)
            return 2 if any(item["severity"] in {"critical", "high"} for item in findings) else 0
        if args.command == "guard":
            return command_guard(args)
        if args.command == "github-doctor":
            result = github_doctor(root, args.repair)
            print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else ("Connection ready." if result["ready"] else "Connection setup required."))
            return 0 if result["ready"] else 2
        if args.command == "safe-commit":
            return command_safe_commit(args)
        if args.command == "safe-push":
            return command_safe_push(args)
        if args.command == "protect":
            return command_protect(args)
    except AgentCtlError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
