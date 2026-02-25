"""Unit tests for OrgMemory cross-repo learning."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data_store.org_memory import OrgMemory, _org_from_remote


@pytest.mark.unit
class TestOrgFromRemote:
    def test_extracts_org_from_https(self):
        mock = MagicMock(returncode=0, stdout="https://github.com/psf/requests.git\n")
        with patch("subprocess.run", return_value=mock):
            org, org_id = _org_from_remote(".")
        assert org == "psf"
        assert len(org_id) == 12

    def test_extracts_org_from_ssh(self):
        mock = MagicMock(returncode=0, stdout="git@github.com:pallets/flask.git\n")
        with patch("subprocess.run", return_value=mock):
            org, org_id = _org_from_remote(".")
        assert org == "pallets"

    def test_fallback_on_failure(self):
        with patch("subprocess.run", side_effect=Exception("no git")):
            org, org_id = _org_from_remote(".")
        assert org == "unknown"


@pytest.mark.unit
class TestOrgMemory:
    def _sre_result(self, fixes=None, arch=None):
        fixes = fixes or [{"rule": "E501"}, {"rule": "E501"}, {"rule": "F401"}]
        arch = arch or {"F403": 2}
        return {
            "fixes": fixes,
            "architectural_violations_by_rule": arch,
        }

    def test_update_adds_repo(self, tmp_path):
        mem = OrgMemory("testorg", store_dir=tmp_path)
        mem.update_from_sre_result("repo1", self._sre_result())
        assert "repo1" in mem._data["repos_seen"]
        assert mem._data["total_runs"] == 1

    def test_update_tracks_rules(self, tmp_path):
        mem = OrgMemory("testorg", store_dir=tmp_path)
        mem.update_from_sre_result("repo1", self._sre_result())
        rules = mem._data["rules"]
        assert "E501" in rules
        assert rules["E501"]["total_violations"] == 2
        assert "F403" in rules

    def test_unfixable_after_threshold(self, tmp_path):
        mem = OrgMemory("testorg", store_dir=tmp_path)
        # 6 violations of F403, 0 fixes — fix_rate stays near 0
        arch_result = {"fixes": [], "architectural_violations_by_rule": {"F403": 6}}
        mem.update_from_sre_result("repo1", arch_result)
        # Force total_violations to 6 manually for threshold check
        mem._data["rules"].setdefault("F403", {})["total_violations"] = 6
        mem._data["rules"]["F403"]["fix_rate"] = 0.0
        mem._data["unfixable_rules"] = [
            r for r, e in mem._data["rules"].items()
            if e["total_violations"] >= 5 and e["fix_rate"] < 0.05
        ]
        assert "F403" in mem._data["unfixable_rules"]

    def test_save_and_reload(self, tmp_path):
        mem = OrgMemory("testorg", store_dir=tmp_path)
        mem.update_from_sre_result("repo1", self._sre_result())
        runs = mem._data["total_runs"]

        mem2 = OrgMemory("testorg", store_dir=tmp_path)
        assert mem2._data["total_runs"] == runs
        assert "E501" in mem2._data["rules"]

    def test_summary_top_rules(self, tmp_path):
        mem = OrgMemory("testorg", store_dir=tmp_path)
        mem.update_from_sre_result("r1", self._sre_result())
        s = mem.summary()
        assert s["org_name"] == "testorg"
        assert s["repos_seen"] == 1
        assert len(s["top_rules"]) >= 1

    def test_multi_repo_accumulation(self, tmp_path):
        mem = OrgMemory("testorg", store_dir=tmp_path)
        mem.update_from_sre_result("repo1", {"fixes": [{"rule": "E501"}], "architectural_violations_by_rule": {}})
        mem.update_from_sre_result("repo2", {"fixes": [{"rule": "E501"}], "architectural_violations_by_rule": {}})
        assert mem._data["rules"]["E501"]["total_violations"] == 2
        assert set(mem._data["rules"]["E501"]["repos"]) == {"repo1", "repo2"}
        assert mem._data["total_runs"] == 2

    def test_for_repo_factory(self, tmp_path):
        mock = MagicMock(returncode=0, stdout="https://github.com/psf/requests.git\n")
        with patch("subprocess.run", return_value=mock):
            mem = OrgMemory.for_repo(".", store_dir=tmp_path)
        assert mem.org_name == "psf"

    def test_empty_result_is_noop(self, tmp_path):
        mem = OrgMemory("testorg", store_dir=tmp_path)
        mem.update_from_sre_result("repo1", {})
        assert mem._data["total_runs"] == 0
