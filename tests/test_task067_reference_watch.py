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
    if url.endswith("/"):
        url = url[:-1]
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
        if url.rstrip("/").endswith("/repos/alientek-openedv/atk-logic"):
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
    # Running the dry stub audit does not open the native DLL, capture, or write files.
    monkeypatch.setattr(refcheck, "github_json", lambda *_a, **_kw: pytest.fail("Unexpected network"))
    result = refcheck.audit(refcheck.load_manifest(), fake_response)
    assert not result["repin_performed"]
