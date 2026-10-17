"""TASK-067 reference watcher: deterministic offline API stubs, never network/USB."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

FILE = Path(__file__).resolve().parents[1] / "scripts/check_dl16_references.py"
spec = importlib.util.spec_from_file_location("check_dl16_references", FILE)
assert spec and spec.loader
refcheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refcheck)


def fake_response(url):
    if url.endswith("/pulls/4") or url.endswith("/pulls/5"):
        return {"state": "open", "merged": False, "title": "pending", "head": {"sha": "9" * 40},
                "updated_at": "2026-05-14T00:00:00Z"}
    if "/compare/" in url:
        return {"status": "identical", "ahead_by": 0, "behind_by": 0}
    if "/commits/" in url:
        base = url.split("/repos/")[1].split("/commits/")[0]
        item = next(x for x in refcheck.load_manifest()["repositories"] if x["repo"] == base)
        return {"sha": item["pin"], "commit": {"committer": {"date": "2026-10-17T00:00:00Z"}}}
    if "/repos/" in url:
        base = url.split("/repos/")[1]
        item = next(x for x in refcheck.load_manifest()["repositories"] if x["repo"] == base)
        return {"default_branch": item["branch"]}
    raise AssertionError(f"unexpected stub URL {url}")


def test_manifest_has_exactly_five_pins_and_watched_prs():
    manifest = refcheck.load_manifest()
    assert len(manifest["repositories"]) == 5
    assert len({x["repo"] for x in manifest["repositories"]}) == 5
    assert {(x["repo"], x["number"]) for x in manifest["pull_requests"]} == {
        ("alientek-openedv/atk-logic", 4), ("alientek-openedv/atk-logic", 5)}


def test_all_unchanged_no_false_hil_claim():
    report = refcheck.audit(refcheck.load_manifest(), fake_response)
    assert report["unchanged"] == 5
    assert report["drift"] == 0 and report["unknown"] == 0
    assert report["repin_performed"] is False
    assert report["physical_hil_performed"] is False
    assert [x["status"] for x in report["pull_requests"]] == ["OPEN", "OPEN"]
    assert "UNKNOWN is not UNCHANGED" in refcheck.as_markdown(report)


def test_real_commit_drift_is_reported():
    def changed(url):
        if "/compare/" in url and "LHX369963" in url:
            return {"status": "ahead", "ahead_by": 2, "behind_by": 0}
        if "/commits/" in url and "LHX369963" in url:
            return {"sha": "1" * 40, "commit": {"committer": {"date": "2026-10-17"}}}
        return fake_response(url)
    result = refcheck.audit(refcheck.load_manifest(), changed)
    assert result["unchanged"] == 4
    assert result["drift"] == 1
    assert next(x for x in result["repositories"] if x["project"] == "LHX")["status"] == "DRIFT"


def test_unavailable_api_is_unknown_not_clean():
    def unavailable(url):
        if "/compare/" in url and "gjjisadog" in url:
            raise refcheck.RemoteCheckError("GitHub API limited")
        return fake_response(url)
    report = refcheck.audit(refcheck.load_manifest(), unavailable)
    assert report["unknown"] == 1
    assert report["unchanged"] == 4
    assert next(x for x in report["repositories"] if x["project"] == "CPP")["status"] == "UNKNOWN"


def test_branch_change_is_drift_without_compare():
    def new_branch(url):
        if url == "https://api.github.com/repos/alientek-openedv/atk-logic":
            return {"default_branch": "main"}
        return fake_response(url)
    result = refcheck.audit(refcheck.load_manifest(), new_branch)
    assert result["drift"] == 1
    assert next(x for x in result["repositories"] if x["project"] == "VENDOR")["status"] == "DRIFT"


def test_invalid_manifest_fails_closed(tmp_path):
    src = refcheck.load_manifest()
    src["repositories"][0]["pin"] = "not_sha"
    manifest = tmp_path / "pins.json"
    manifest.write_text(json.dumps(src))
    with pytest.raises(ValueError):
        refcheck.load_manifest(manifest)


def test_readonly_check_never_auto_upgrades(monkeypatch):
    # Default getter is resolved at call time, so a patched github_json is the
    # only network path. The audit still never repins or claims physical HIL.
    calls = []

    def tracking(url):
        calls.append(url)
        return fake_response(url)

    monkeypatch.setattr(refcheck, "github_json", tracking)
    result = refcheck.audit(refcheck.load_manifest())
    assert calls
    assert all(url.startswith("https://api.github.com/repos/") and not url.endswith("/") for url in calls)
    assert result["repin_performed"] is False
    assert result["physical_hil_performed"] is False


@pytest.mark.parametrize(
    ("repo", "suffix"),
    [
        ("alientek-openedv/atk-logic", ""),
        ("LHX369963/dl16-cli", "compare/8d7c209c1e3b13923620bb34cec915291a749612...master"),
    ],
)
def test_url_accepts_compare_triple_dot_and_repo_root(repo, suffix):
    assert refcheck._url(repo, suffix) == "https://api.github.com/repos/" + repo + (
        "/" + suffix if suffix else "")


def test_empty_suffix_is_repo_url_without_trailing_slash():
    repo = "gjjisadog/ATK-Logic-Mcp"
    assert refcheck._url(repo, "") == "https://api.github.com/repos/" + repo


def test_repo_re_allows_embedded_dots():
    assert refcheck.REPO_RE.fullmatch("foo.bar/baz.qux")
    assert refcheck._url("foo.bar/baz.qux", "") == "https://api.github.com/repos/foo.bar/baz.qux"


@pytest.mark.parametrize("suffix", ["../x", "a/./b"])
def test_url_rejects_dot_path_segments(suffix):
    with pytest.raises(ValueError):
        refcheck._url("alientek-openedv/atk-logic", suffix)


@pytest.mark.parametrize("repo", ["../..", "./.", "foo/..", "../bar"])
def test_repo_re_rejects_dot_only_owner_or_name(repo):
    assert refcheck.REPO_RE.fullmatch(repo) is None
    with pytest.raises(ValueError):
        refcheck._url(repo, "")


def test_merged_pr_is_merged_and_closed_pr_is_drift():
    def merged(url):
        if url.endswith("/pulls/4"):
            return {"state": "closed", "merged": True, "merged_at": "2026-10-17T00:00:00Z",
                    "title": "landed", "head": {"sha": "a" * 40},
                    "updated_at": "2026-10-17T00:00:00Z"}
        if url.endswith("/pulls/5"):
            return {"state": "closed", "merged": False, "merged_at": None,
                    "title": "declined", "head": {"sha": "b" * 40},
                    "updated_at": "2026-10-17T00:00:00Z"}
        return fake_response(url)

    report = refcheck.audit(refcheck.load_manifest(), merged)
    by_number = {pr["number"]: pr for pr in report["pull_requests"]}
    assert by_number[4]["status"] == "MERGED" and by_number[4]["merged"] is True
    assert by_number[5]["status"] == "CLOSED" and by_number[5]["merged"] is False
    assert report["drift"] == 2
    assert report["unknown"] == 0
    rendered = refcheck.as_markdown(report)
    assert "MERGED" in rendered and "CLOSED" in rendered


def test_main_exit_codes(monkeypatch, tmp_path):
    calls = []

    def unchanged(url):
        calls.append(url)
        return fake_response(url)

    monkeypatch.setattr(refcheck, "github_json", unchanged)
    assert refcheck.main([]) == 0
    assert calls

    def drifted(url):
        if "/compare/" in url and "LHX369963" in url:
            return {"status": "ahead", "ahead_by": 1, "behind_by": 0}
        if "/commits/" in url and "LHX369963" in url:
            return {"sha": "1" * 40, "commit": {"committer": {"date": "2026-10-17"}}}
        return fake_response(url)

    monkeypatch.setattr(refcheck, "github_json", drifted)
    assert refcheck.main([]) == 2

    def merged_pr(url):
        if url.endswith("/pulls/4"):
            return {"state": "closed", "merged": True, "title": "landed",
                    "head": {"sha": "c" * 40}, "updated_at": "2026-10-17T00:00:00Z"}
        return fake_response(url)

    monkeypatch.setattr(refcheck, "github_json", merged_pr)
    assert refcheck.main([]) == 2

    def offline(url):
        raise refcheck.RemoteCheckError("offline")

    monkeypatch.setattr(refcheck, "github_json", offline)
    assert refcheck.main([]) == 3

    src = refcheck.load_manifest()
    src["schema"] = "not-the-watch-schema"
    manifest = tmp_path / "bad.json"
    manifest.write_text(json.dumps(src), encoding="utf-8")
    assert refcheck.main(["--manifest", str(manifest)]) == 4
