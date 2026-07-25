"""A configuração desejada é dado, não código, e sabe dizer o que ainda não foi decidido."""

import json
from pathlib import Path
from typing import Any

import pytest

from panlabs.ruleset.config import DEFAULT_CONFIG_PATH, Desired, load_desired

FIXTURES = Path(__file__).parent / "fixtures"


def rules_of(want: Desired) -> dict[str, Any]:
    assert want.ruleset is not None
    return {rule["type"]: rule.get("parameters") or {} for rule in want.ruleset["rules"]}


def test_the_config_shipped_in_this_repo_carries_the_whole_gate_decided_by_spec_org_2():
    """O gate inteiro é uma decisão só, e ela mora no dado: nada aqui sobrou null."""
    want = load_desired(DEFAULT_CONFIG_PATH)

    assert want.undecided == ()
    assert want.is_decided
    assert want.retire_classic_protection is True
    assert want.ruleset is not None
    assert want.ruleset["enforcement"] == "active"
    assert want.ruleset["bypass_actors"] == []

    rules = rules_of(want)
    assert set(rules) == {
        "deletion",
        "non_fast_forward",
        "pull_request",
        "required_linear_history",
        "required_signatures",
        "required_status_checks",
    }
    assert rules["pull_request"]["required_approving_review_count"] == 0
    assert rules["pull_request"]["allowed_merge_methods"] == ["squash"]
    assert rules["required_status_checks"]["strict_required_status_checks_policy"] is True
    contexts = rules["required_status_checks"]["required_status_checks"]
    assert [check["context"] for check in contexts] == ["checks", "security"]


def test_signature_and_squash_only_are_one_decision_and_land_in_the_same_config():
    """Exigir assinatura sem restringir a squash quebraria o merge autônomo na hora."""
    want = load_desired(DEFAULT_CONFIG_PATH)

    assert "required_signatures" in rules_of(want)
    assert want.repo_settings is not None
    assert want.repo_settings["allow_squash_merge"] is True
    assert want.repo_settings["allow_merge_commit"] is False
    assert want.repo_settings["allow_rebase_merge"] is False


def test_the_config_also_decides_branch_deletion_on_merge_and_auto_merge():
    """Auto-merge é pré-requisito técnico do Dependabot com auto-merge, da issue seguinte."""
    want = load_desired(DEFAULT_CONFIG_PATH)

    assert want.repo_settings is not None
    assert want.repo_settings["delete_branch_on_merge"] is True
    assert want.repo_settings["allow_auto_merge"] is True


def test_the_check_contract_is_read_from_the_desired_data_not_written_in_code():
    want = load_desired(DEFAULT_CONFIG_PATH)

    assert want.check_contract == ("checks", "security")


def test_a_desired_state_without_a_ruleset_declares_no_check_contract_at_all():
    assert Desired().check_contract == ()


def test_a_filled_config_reports_nothing_undecided():
    want = load_desired(FIXTURES / "desired-ruleset.json")

    assert want.undecided == ()
    assert want.is_decided
    assert want.retire_classic_protection is True


def test_an_undecided_repo_settings_is_reported_as_pending_like_any_other_dimension(
    tmp_path: Path,
):
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps({"repo_settings": None}), encoding="utf-8")

    want = load_desired(path)

    assert want.repo_settings is None
    assert "repo_settings" in want.undecided


def test_an_unknown_key_is_rejected_so_a_typo_never_passes_as_undecided(tmp_path: Path):
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps({"rulset": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="rulset"):
        load_desired(path)


def test_an_unknown_repo_setting_is_rejected_because_the_api_would_ignore_it_in_silence(
    tmp_path: Path,
):
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps({"repo_settings": {"allow_squash_merges": True}}), encoding="utf-8")

    with pytest.raises(ValueError, match="allow_squash_merges"):
        load_desired(path)


def test_a_ruleset_without_the_fields_the_planner_compares_is_rejected(tmp_path: Path):
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps({"ruleset": {"name": "panlabs"}}), encoding="utf-8")

    with pytest.raises(ValueError, match="rules"):
        load_desired(path)


def test_keys_prefixed_with_underscore_are_notes_for_humans_and_are_ignored(tmp_path: Path):
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps({"_nota": "qualquer coisa"}), encoding="utf-8")

    assert load_desired(path) == Desired()


def test_the_only_desired_configuration_that_ships_is_the_full_gate():
    """A configuração mínima da #8 foi aposentada: aplicá-la hoje desfaria o gate."""
    config_dir = Path(__file__).resolve().parents[1] / "config"

    assert not (config_dir / "ruleset-dotgithub-required-checks.json").exists()
    assert load_desired(config_dir / "ruleset.json").is_decided
