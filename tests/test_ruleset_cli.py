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
FLEET_WITH_PRIVATE = FIXTURES / "fleet-2026-07-27.json"
DESIRED = FIXTURES / "desired-ruleset.json"
SHIPPED = Path(__file__).resolve().parents[1] / "config" / "ruleset.json"


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
    assert "18 itens em 7 alvo(s)." in capsys.readouterr().out


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


def test_an_empty_plan_from_an_undecided_config_does_not_claim_conformance(
    forbid_api: None, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    undecided = tmp_path / "ruleset.json"
    undecided.write_text(
        json.dumps({"ruleset": None, "repo_settings": None, "retire_classic_protection": None}),
        encoding="utf-8",
    )

    code = main(["--observed", str(FLEET), "--config", str(undecided)])

    captured = capsys.readouterr()

    assert code == 0
    assert "Nada a fazer" in captured.out
    assert "NÃO quer dizer que a frota está conforme" in captured.out
    assert "ainda sem decisão" in captured.err


def test_the_config_shipped_in_this_repo_no_longer_reports_anything_undecided(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """A spec de Org #2 já decidiu: rodar com o dado versionado não avisa nada pendente."""
    main(["--observed", str(FLEET), "--config", str(SHIPPED)])

    assert "ainda sem decisão" not in capsys.readouterr().err


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

    assert len(payload["items"]) == 18
    assert {"action", "target", "reason", "payload", "hold"} == set(payload["items"][0])


# --- o portão: a frota inteira é planejada, e só parte dela é aplicada -------


def test_a_full_fleet_run_shows_the_divergence_of_a_repo_it_will_not_touch(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    main(["--observed", str(FLEET), "--config", str(DESIRED)])

    out = capsys.readouterr().out

    assert "panlabs-tech/travelmanager" in out
    assert "retido" in out
    assert "a CI dele não publica com esse nome" in out


def test_apply_without_only_touches_just_the_repos_that_already_speak_the_contract(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """O portão é o que torna seguro rodar `--apply` contra a org viva sem `--only`."""
    raw = json.loads(FLEET.read_text(encoding="utf-8"))
    monkeypatch.setattr("panlabs.ruleset.cli.fetch_raw", lambda _org: raw)
    calls: list[str] = []
    monkeypatch.setattr(gh, "api", lambda path, **_kwargs: calls.append(path))

    code = main(["--config", str(DESIRED), "--apply"])

    assert code == 0
    touched = {
        path.removeprefix("repos/").split("/rulesets")[0].split("/branches")[0] for path in calls
    }
    assert touched == {"panlabs-tech/.github", "panlabs-tech/panlabs"}


def test_apply_of_a_plan_entirely_held_says_so_instead_of_claiming_it_applied(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    raw = json.loads(FLEET.read_text(encoding="utf-8"))
    raw["repos"] = [r for r in raw["repos"] if r["name"] == "panlabs-tech/skills"]
    monkeypatch.setattr("panlabs.ruleset.cli.fetch_raw", lambda _org: raw)
    monkeypatch.setattr(gh, "api", lambda *_a, **_k: pytest.fail("aplicou um item retido"))

    code = main(["--config", str(DESIRED), "--apply"])

    err = capsys.readouterr().err
    assert code == 0
    assert "Nada a aplicar" in err
    assert "retidos" in err


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
    assert "não são avaliados" in captured.err
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

    assert "não são avaliados" not in capsys.readouterr().err


def test_naming_a_repo_in_only_lifts_the_hold_that_would_otherwise_defer_it(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """Nomear o repo é o operador afirmando que a CI dele já publica os nomes fixos."""
    argv = ["--observed", str(FLEET), "--config", str(DESIRED), "--only", "panlabs-tech/skills"]

    main([*argv, "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["items"]
    assert all(item["hold"] == "" for item in payload["items"])


def test_only_with_a_name_that_is_not_in_the_org_fails_instead_of_planning_nothing(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """Plano vazio por causa de um erro de digitação se leria como "já converge"."""
    code = main(
        ["--observed", str(FLEET), "--config", str(DESIRED), "--only", "panlabs-tech/skils"]
    )

    assert code == 1
    assert "panlabs-tech/skils" in capsys.readouterr().err


def test_every_action_the_planner_can_emit_has_an_effect_registered():
    """Uma ação sem efeito só falharia na hora de aplicar, tarde demais."""
    emitted = {
        planner.CREATE_RULESET,
        planner.UPDATE_RULESET,
        planner.DELETE_RULESET,
        planner.DELETE_CLASSIC_PROTECTION,
        planner.UPDATE_REPO_SETTINGS,
    }

    assert set(EFFECTS) == emitted


# --- o resumo não afirma nada sobre o que ninguém mediu ------------------------


def test_the_summary_separates_what_was_not_observed_from_what_has_no_protection(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """ "Nenhum ruleset governa esta branch" e "ninguém leu esta branch" são opostos.

    Contá-los na mesma coluna faria a linha de resumo dizer que a frota tem um
    repositório desprotegido, ou um protegido, sem que nenhuma das duas tenha sido
    observada.
    """
    code = main(["--observed", str(FLEET_WITH_PRIVATE), "--config", str(DESIRED)])
    out = capsys.readouterr().out

    assert code == 0
    assert (
        "8 repo(s) na org viva, 3 com ruleset na branch default, "
        "4 com proteção clássica, 1 sem observação de proteção." in out
    )


def test_the_whole_fleet_still_gets_a_plan_with_an_unreadable_repo_in_it(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """Antes deste conserto o comando saía com erro e plano nenhum."""
    code = main(["--observed", str(FLEET_WITH_PRIVATE), "--config", str(DESIRED)])

    assert code == 0
    assert planner.OBSERVE_PROTECTION in capsys.readouterr().out
