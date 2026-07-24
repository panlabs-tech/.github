"""A configuração desejada é dado, não código, e sabe dizer o que ainda não foi decidido."""

import json
from pathlib import Path

import pytest

from panlabs.ruleset.config import DEFAULT_CONFIG_PATH, Desired, load_desired

FIXTURES = Path(__file__).parent / "fixtures"


def test_the_config_shipped_in_this_repo_is_the_skeleton_that_spec_org_2_fills():
    want = load_desired(DEFAULT_CONFIG_PATH)

    assert want.ruleset is None
    assert want.retire_classic_protection is None
    assert want.undecided == ("retire_classic_protection", "ruleset")
    assert not want.is_decided


def test_a_filled_config_reports_nothing_undecided():
    want = load_desired(FIXTURES / "desired-ruleset.json")

    assert want.undecided == ()
    assert want.is_decided
    assert want.retire_classic_protection is True


def test_an_unknown_key_is_rejected_so_a_typo_never_passes_as_undecided(tmp_path: Path):
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps({"rulset": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="rulset"):
        load_desired(path)


def test_a_ruleset_without_the_fields_the_planner_compares_is_rejected(tmp_path: Path):
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps({"ruleset": {"name": "panlabs"}}), encoding="utf-8")

    with pytest.raises(ValueError, match="rules"):
        load_desired(path)


def test_keys_prefixed_with_underscore_are_notes_for_humans_and_are_ignored(tmp_path: Path):
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps({"_nota": "qualquer coisa"}), encoding="utf-8")

    assert load_desired(path) == Desired(ruleset=None, retire_classic_protection=None)
