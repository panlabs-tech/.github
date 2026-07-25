"""A configuração desejada de org é dado, e sabe dizer o que ainda não foi decidido."""

import json
from pathlib import Path

import pytest

from panlabs.org.config import DEFAULT_CONFIG_PATH, KNOWN_KEYS, Desired, load_desired

FIXTURES = Path(__file__).parent / "fixtures"


def test_the_config_shipped_in_this_repo_decides_every_dimension():
    """Esta issue é a execução da spec de Org #2: aqui o dado não fica em aberto."""
    want = load_desired(DEFAULT_CONFIG_PATH)

    assert want.undecided == ()
    assert want.is_decided


def test_the_shipped_config_re_enables_the_policy_that_broke_the_esteira():
    want = load_desired(DEFAULT_CONFIG_PATH)

    assert want.actions_can_approve_pull_requests is True


def test_the_wiki_exception_is_declared_data_and_names_the_release_automation_repo():
    want = load_desired(DEFAULT_CONFIG_PATH)

    assert want.wiki is not None
    assert want.wiki["enabled"] is False
    assert want.wiki_exceptions() == frozenset({"panlabs-tech/tfbox"})


def test_an_empty_config_reports_every_dimension_as_undecided():
    """Nenhuma dimensão vem decidida por default: dado ausente é dado ausente."""
    want = Desired()

    assert want.undecided == tuple(sorted(KNOWN_KEYS))
    assert not want.is_decided
    assert want.wiki_exceptions() == frozenset()


def test_an_unknown_key_is_rejected_so_a_typo_never_passes_as_undecided(tmp_path: Path):
    path = tmp_path / "org.json"
    path.write_text(json.dumps({"puhs_protection": True}), encoding="utf-8")

    with pytest.raises(ValueError, match="puhs_protection"):
        load_desired(path)


def test_a_wiki_dimension_without_its_exception_list_is_rejected(tmp_path: Path):
    """Esquecer a lista desligaria o wiki gerado por automação de release."""
    path = tmp_path / "org.json"
    path.write_text(json.dumps({"wiki": {"enabled": False}}), encoding="utf-8")

    with pytest.raises(ValueError, match="exceptions"):
        load_desired(path)


def test_an_empty_exception_list_is_a_decision_and_is_accepted(tmp_path: Path):
    path = tmp_path / "org.json"
    path.write_text(json.dumps({"wiki": {"enabled": False, "exceptions": []}}), encoding="utf-8")

    assert load_desired(path).wiki_exceptions() == frozenset()


def test_keys_prefixed_with_underscore_are_notes_for_humans_and_are_ignored(tmp_path: Path):
    path = tmp_path / "org.json"
    path.write_text(json.dumps({"_nota": "qualquer coisa"}), encoding="utf-8")

    assert load_desired(path) == Desired()


def test_the_fixture_used_by_the_planner_tests_mirrors_the_shipped_shape():
    """Se as duas divergirem de forma, o teste do planner deixa de medir o real."""
    shipped = load_desired(DEFAULT_CONFIG_PATH)
    fixture = load_desired(FIXTURES / "desired-org.json")

    assert fixture.is_decided
    assert set(fixture.repo_topics or {}) == set(shipped.repo_topics or {})
    assert fixture.wiki_exceptions() == shipped.wiki_exceptions()
