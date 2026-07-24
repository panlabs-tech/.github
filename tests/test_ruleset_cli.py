"""A interface: o contrato de que rodar sem argumento nunca muda nada.

O applier em si não é testado: ele é fino por construção. O que se testa aqui é
a fronteira: que o caminho de plano não chega nele, e que a tabela de efeitos
cobre exatamente o vocabulário de ações que o planner sabe emitir.
"""

import json
from pathlib import Path

import pytest

from panlabs import gh
from panlabs.ruleset import planner
from panlabs.ruleset.applier import EFFECTS
from panlabs.ruleset.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
FLEET = FIXTURES / "fleet-2026-07-24.json"
DESIRED = FIXTURES / "desired-ruleset.json"
SKELETON = Path(__file__).resolve().parents[1] / "config" / "ruleset.json"


@pytest.fixture
def forbid_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Qualquer toque na API durante um plano é falha de teste, não detalhe."""

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("o caminho de plano chamou a API")

    monkeypatch.setattr(gh, "api", explode)


def test_running_without_apply_reaches_no_api_at_all(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    code = main(["--observed", str(FLEET), "--config", str(DESIRED)])

    assert code == 0
    assert "11 itens em 7 alvo(s)." in capsys.readouterr().out


def test_the_plan_the_operator_reads_names_action_target_and_reason(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    main(["--observed", str(FLEET), "--config", str(DESIRED)])

    out = capsys.readouterr().out

    assert "panlabs-tech/tfbox" in out
    assert "delete-classic-protection" in out
    assert "proteção clássica ativa em main" in out


def test_apply_refuses_a_saved_snapshot_because_the_org_may_have_moved(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    code = main(["--apply", "--observed", str(FLEET), "--config", str(DESIRED)])

    assert code == 2
    assert "--apply não aceita --observed" in capsys.readouterr().err


def test_an_empty_plan_from_the_undecided_skeleton_does_not_claim_conformance(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    code = main(["--observed", str(FLEET), "--config", str(SKELETON)])

    captured = capsys.readouterr()

    assert code == 0
    assert "Nada a fazer" in captured.out
    assert "NÃO quer dizer que a frota está conforme" in captured.out
    assert "ainda sem decisão" in captured.err


def test_a_decided_config_with_nothing_to_do_does_say_the_fleet_converges(
    forbid_api: None, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    empty_org = tmp_path / "observed.json"
    empty_org.write_text(json.dumps({"org": "panlabs-tech", "repos": []}), encoding="utf-8")

    main(["--observed", str(empty_org), "--config", str(DESIRED)])

    assert "já converge com o desejado" in capsys.readouterr().out


def test_json_output_is_the_serialized_plan_and_nothing_else(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    main(["--observed", str(FLEET), "--config", str(DESIRED), "--json"])

    payload = json.loads(capsys.readouterr().out)

    assert len(payload["items"]) == 11
    assert {"action", "target", "reason", "payload"} == set(payload["items"][0])


# --- --only: restringe o plano a um subconjunto explícito da frota -----------


def test_only_restricts_the_plan_to_the_named_repo_and_reports_who_is_left_out(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    code = main(
        ["--observed", str(FLEET), "--config", str(DESIRED), "--only", "panlabs-tech/.github"]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "panlabs-tech/.github" in captured.out
    assert "panlabs-tech/skills" not in captured.out
    assert "aguardando retrofit" in captured.err
    assert "panlabs-tech/skills" in captured.err


def test_only_accepts_more_than_one_repo(forbid_api: None, capsys: pytest.CaptureFixture[str]):
    main(
        [
            "--observed",
            str(FLEET),
            "--config",
            str(DESIRED),
            "--only",
            "panlabs-tech/.github",
            "--only",
            "panlabs-tech/tfbox",
        ]
    )

    out = capsys.readouterr().out
    assert "panlabs-tech/.github" in out
    assert "panlabs-tech/tfbox" in out
    assert "panlabs-tech/skills" not in out


def test_only_naming_the_whole_fleet_reports_nothing_left_out(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    fleet_raw = json.loads(FLEET.read_text(encoding="utf-8"))
    all_repos = {r["name"] for r in fleet_raw["repos"]}
    argv = ["--observed", str(FLEET), "--config", str(DESIRED)]
    for name in all_repos:
        argv += ["--only", name]

    main(argv)

    assert "aguardando retrofit" not in capsys.readouterr().err


def test_every_action_the_planner_can_emit_has_an_effect_registered():
    """Uma ação sem efeito só falharia na hora de aplicar, tarde demais."""
    emitted = {
        planner.CREATE_RULESET,
        planner.UPDATE_RULESET,
        planner.DELETE_RULESET,
        planner.DELETE_CLASSIC_PROTECTION,
    }

    assert set(EFFECTS) == emitted
