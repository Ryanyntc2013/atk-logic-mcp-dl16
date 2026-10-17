"""Read-only audit of five pinned DL16 reference projects and selected vendor PRs.

No checkout, USB, device, file mutation, auto-repin, or network access in tests.
The only live network path is public GitHub REST when the operator runs the script.

Exit codes:
  0  every pinned repository is UNCHANGED and every watched PR is still OPEN
  2  drift: a pin or default branch moved, or a watched PR is no longer OPEN
     (CLOSED, or MERGED when GitHub reports the pull request as merged)
  3  inconclusive: a repository or PR check is UNKNOWN after a network/API
     failure. UNKNOWN is not UNCHANGED. This code wins over drift.
  4  the manifest is missing or invalid, so no network result was produced
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MANIFEST = Path(__file__).resolve().parents[1] / "docs/research/dl16-reference-watch.json"
# Owner and repo are one segment each. "." and ".." are path traversal, not names.
# Embedded dots (foo.bar) stay legal; compare "..." is a suffix, not a repo segment.
_SEGMENT = r"(?!\.(?:/|$))(?!\.\.(?:/|$))[A-Za-z0-9_.-]+"
REPO_RE = re.compile(rf"^{_SEGMENT}/{_SEGMENT}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class RemoteCheckError(RuntimeError):
    pass


def _url(repo: str, suffix: str) -> str:
    if (not REPO_RE.fullmatch(repo) or
            any(part in (".", "..") for part in suffix.split("/"))):
        raise ValueError("Invalid fixed reference URL")
    tail = suffix.lstrip("/")
    base = f"https://api.github.com/repos/{repo}"
    # GitHub returns 404 for /repos/{owner}/{repo}/ ; the root resource has no slash.
    return f"{base}/{tail}" if tail else base


def _resolve_getter(getter: Callable[[str], dict] | None) -> Callable[[str], dict]:
    # Look up github_json at call time so tests can replace it after import.
    return github_json if getter is None else getter


def github_json(url: str, *, timeout: float = 12) -> dict[str, Any]:
    if not url.startswith("https://api.github.com/repos/"):
        raise RemoteCheckError("Only GitHub repository API paths permitted")
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "DL16-upstream-reference-audit"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with urlopen(Request(url, headers=headers), timeout=timeout) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise RemoteCheckError("Expected JSON object from GitHub")
        return result
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise RemoteCheckError(f"Cannot verify GitHub API resource: {type(exc).__name__}: {exc}") from exc


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "dl16-reference-watch/v1":
        raise ValueError("Unexpected reference manifest schema")
    for item in manifest["repositories"]:
        if not REPO_RE.fullmatch(item["repo"]) or not SHA_RE.fullmatch(item["pin"]):
            raise ValueError("Invalid pinned GitHub repository entry")
        if item["branch"] not in ("main", "master"):
            raise ValueError("Unsupported branch in pinned reference")
    for pr in manifest.get("pull_requests", []):
        if not REPO_RE.fullmatch(pr["repo"]) or type(pr["number"]) is not int or pr["number"] < 1:
            raise ValueError("Invalid watched PR")
    return manifest


def check_reference(item: dict, getter: Callable[[str], dict] | None = None) -> dict:
    getter = _resolve_getter(getter)
    repo, branch, pin = item["repo"], item["branch"], item["pin"]
    result = {"project": item["key"], "repository": repo, "pin": pin, "branch": branch}
    try:
        meta = getter(_url(repo, ""))
        actual_branch = meta.get("default_branch")
        if not actual_branch or actual_branch != branch:
            return {**result, "status": "DRIFT", "reason": "Default branch changed",
                    "actual_default_branch": actual_branch}
        head = getter(_url(repo, f"commits/{branch}"))
        comparison = getter(_url(repo, f"compare/{pin}...{branch}"))
        sha = head.get("sha")
        ahead = comparison.get("ahead_by")
        behind = comparison.get("behind_by")
        status = comparison.get("status")
        if not SHA_RE.fullmatch(str(sha)) or not isinstance(ahead, int) or not isinstance(behind, int):
            raise RemoteCheckError("Incomplete HEAD or compare evidence")
        unchanged = sha == pin and ahead == 0 and behind == 0 and status == "identical"
        return {**result, "status": "UNCHANGED" if unchanged else "DRIFT",
                "head": sha, "last_commit": head.get("commit", {}).get("committer", {}).get("date"),
                "ahead_by": ahead, "behind_by": behind, "compare_status": status}
    except (RemoteCheckError, ValueError, KeyError, TypeError) as exc:
        return {**result, "status": "UNKNOWN", "error": str(exc)}


def check_pr(item: dict, getter: Callable[[str], dict] | None = None) -> dict:
    getter = _resolve_getter(getter)
    result = {"repository": item["repo"], "number": item["number"],
              "topic": item["topic"]}
    try:
        pr = getter(_url(item["repo"], f"pulls/{item['number']}"))
        if not isinstance(pr.get("state"), str):
            raise RemoteCheckError("PR state unavailable")
        merged = bool(pr.get("merged")) or bool(pr.get("merged_at"))
        # A merged PR's GitHub state is "closed"; report MERGED when it landed.
        status = "MERGED" if merged else pr["state"].upper()
        return {**result, "status": status, "merged": merged,
                "title": pr.get("title"),
                "updated_at": pr.get("updated_at"),
                "head": pr.get("head", {}).get("sha")}
    except (RemoteCheckError, ValueError, KeyError, TypeError) as exc:
        return {**result, "status": "UNKNOWN", "error": str(exc)}


def audit(manifest: dict, getter: Callable[[str], dict] | None = None) -> dict:
    getter = _resolve_getter(getter)
    repos = [check_reference(item, getter) for item in manifest["repositories"]]
    prs = [check_pr(item, getter) for item in manifest.get("pull_requests", [])]
    return {"schema": "dl16-reference-audit/v1",
            "observed_utc": datetime.now(timezone.utc).isoformat(),
            "repositories": repos, "pull_requests": prs,
            "unchanged": sum(x["status"] == "UNCHANGED" for x in repos),
            "drift": (sum(x["status"] == "DRIFT" for x in repos)
                      + sum(x["status"] not in ("OPEN", "UNKNOWN") for x in prs)),
            "unknown": sum(x["status"] == "UNKNOWN" for x in repos)
                     + sum(x["status"] == "UNKNOWN" for x in prs),
            "repin_performed": False, "physical_hil_performed": False}


def as_markdown(doc: dict) -> str:
    lines = ["# DL16 reference SHA drift audit", "",
             f"Observed UTC: {doc['observed_utc']}", "",
             "| Project | Status | Current SHA | Fixed SHA |",
             "|---|---|---|---|"]
    for ref in doc["repositories"]:
        lines.append("| " + " | ".join((ref["project"], ref["status"],
                     ref.get("head", "UNKNOWN"), ref["pin"])) + " |")
    lines += ["", "## Watched vendor PRs", ""]
    for pr in doc["pull_requests"]:
        lines.append(f"- {pr['repository']}#{pr['number']}: {pr['status']} - {pr['topic']}")
    lines.extend(["", "No automatic repin, no HIL. UNKNOWN is not UNCHANGED.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, default=MANIFEST)
    p.add_argument("--markdown", action="store_true")
    args = p.parse_args(argv)
    try:
        report = audit(load_manifest(args.manifest))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"REFERENCE_MANIFEST_INVALID: {exc}", file=sys.stderr)
        return 4
    print(as_markdown(report) if args.markdown else json.dumps(report, ensure_ascii=False, indent=2))
    # 2 = known drift, including a watched PR that is no longer OPEN.
    # 3 = UNKNOWN network/API and wins over drift. 4 = invalid manifest.
    return 3 if report["unknown"] else (2 if report["drift"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
