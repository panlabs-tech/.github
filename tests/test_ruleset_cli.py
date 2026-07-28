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
DOTFILES = "panlabs-tech/dotfiles"


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
    assert "os checks exigidos hoje em" in out


def test_the_hold_reason_names_the_criterion_it_used_and_not_one_it_never_read(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """O motivo apresentava um proxy como fato, e mandava o operador esperar errado.

    O critério é `required_check_contexts()`, os checks que a **proteção atual**
    exige. O texto entregue dizia "a CI dele não publica com esse nome", que é uma
    afirmação sobre um workflow que este script nunca leu. Um repo sem proteção
    nenhuma cai na retenção pela comparação vazia, e `panlabs-tech/skills` foi
    retido com essa frase depois do retrofit #37, que é exatamente o que o fez
    publicar os dois nomes do contrato.
    """
    main(["--observed", str(FLEET), "--config", str(DESIRED)])

    out = capsys.readouterr().out

    assert "a CI dele não publica" not in out
    assert "não é observado por este script" in out


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
    """Uma ação sem efeito só falharia na hora de aplicar, tarde demais.

    O conjunto é escrito à mão de propósito: é a declaração do vocabulário que o
    planner sabe emitir, e é ela que obriga quem inventar uma ação nova a dizer,
    aqui, em qual das duas metades ela cai. Tirar a ação do conjunto em vez de
    declará-la retida faria o teste passar sem cobrir nada.
    """
    emitted = {
        planner.CREATE_RULESET,
        planner.UPDATE_RULESET,
        planner.DELETE_RULESET,
        planner.DELETE_CLASSIC_PROTECTION,
        planner.UPDATE_REPO_SETTINGS,
        planner.OBSERVE_PROTECTION,
    }

    assert set(EFFECTS) == emitted - planner.ALWAYS_HELD


def test_no_always_held_action_has_an_effect_pretending_to_apply_it():
    """Não existe chamada de API que torne um repositório observável."""
    assert set(EFFECTS) & planner.ALWAYS_HELD == set()


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


# --- o que `--apply` diz de um plano que ele não vai aplicar -------------------


@pytest.fixture
def live_fleet_with_private(monkeypatch: pytest.MonkeyPatch) -> None:
    """A org viva, fingida onde o CLI a busca: `--apply` recusa retrato salvo.

    É o único jeito de exercitar o caminho de aplicação sem tocar a rede, e é um
    caminho que precisa de teste: ele é o que fala com o operador **depois** de
    ele ter digitado a flag que muda a org.
    """
    raw = json.loads(FLEET_WITH_PRIVATE.read_text(encoding="utf-8"))
    monkeypatch.setattr("panlabs.ruleset.cli.fetch_raw", lambda _org: raw)


def test_apply_does_not_blame_a_ci_retrofit_for_a_hold_the_platform_caused(
    forbid_api: None, live_fleet_with_private: None, capsys: pytest.CaptureFixture[str]
):
    """Existe mais de uma causa de retenção neste script, e nomear uma só mente.

    Um repo cuja proteção a plataforma recusou a mostrar não está esperando
    retrofit de CI nenhum: nenhum retrofit levanta essa retenção. Mandar o
    operador esperar por ele é pior do que não dizer nada, porque manda esperar
    pela coisa errada.
    """
    code = main(["--apply", "--only", DOTFILES, "--config", str(DESIRED)])
    err = capsys.readouterr().err

    assert code == 0
    assert "retrofit de CI" not in err


def test_apply_reports_each_held_item_with_the_reason_the_planner_wrote(
    forbid_api: None, live_fleet_with_private: None, capsys: pytest.CaptureFixture[str]
):
    """O motivo já está escrito no item; o CLI o entrega, em vez de resumi-lo.

    É o mesmo contrato do CLI de org, e pela mesma razão: quem sabe por que o item
    foi retido é o planner, e qualquer frase que o CLI invente por cima pode
    envelhecer sem que nada acuse.
    """
    main(["--apply", "--only", DOTFILES, "--config", str(DESIRED)])
    err = capsys.readouterr().err

    assert planner.OBSERVE_PROTECTION in err
    assert "Upgrade to GitHub Pro" in err
