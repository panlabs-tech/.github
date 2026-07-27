"""A interface: o contrato de que rodar sem argumento nunca muda nada.

O applier em si não é testado: ele é fino por construção. O que se testa aqui é
a fronteira: que o caminho de plano não chega nele, que a tabela de efeitos
cobre exatamente o vocabulário aplicável, e que o operador é avisado do escopo
de token **antes** de a primeira chamada sair.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from panlabs import gh
from panlabs.org import planner
from panlabs.org.applier import EFFECTS
from panlabs.org.cli import main
from panlabs.org.config import load_desired

FIXTURES = Path(__file__).parent / "fixtures"
FLEET = FIXTURES / "org-fleet-2026-07-24.json"
FLEET_WITH_PRIVATE = FIXTURES / "org-fleet-2026-07-27.json"
DESIRED = FIXTURES / "desired-org.json"


@pytest.fixture
def forbid_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Qualquer toque na API durante um plano é falha de teste, não detalhe."""

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("o caminho de plano chamou a API")

    monkeypatch.setattr(gh, "api", explode)
    monkeypatch.setattr(gh, "graphql", explode)


def converged_snapshot(tmp_path: Path) -> Path:
    """Um retrato da org que já converge com o desejado da fixture, sem repo nenhum."""
    want = load_desired(DESIRED)
    org: dict[str, Any] = {
        "login": "panlabs-tech",
        "description": want.org_description,
        "two_factor_requirement_enabled": True,
    }
    org.update(want.new_repo_security_defaults or {})

    path = tmp_path / "observed.json"
    path.write_text(
        json.dumps(
            {
                "org": org,
                "actions_workflow_permissions": {
                    "default_workflow_permissions": "read",
                    "can_approve_pull_request_reviews": True,
                },
                "pinned_repos": list(want.pinned_repos or ()),
                "repos": [],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_running_without_apply_reaches_no_api_at_all(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    code = main(["--observed", str(FLEET), "--config", str(DESIRED)])

    assert code == 0
    assert "44 itens em 8 alvo(s)." in capsys.readouterr().out


def test_the_plan_the_operator_reads_names_action_target_and_reason(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    main(["--observed", str(FLEET), "--config", str(DESIRED)])

    out = capsys.readouterr().out

    assert "panlabs-tech/tfbox" in out
    assert "set-secret-scanning" in out
    assert "é ele que detecta segredo já commitado" in out


def test_the_summary_says_out_loud_whether_the_esteira_is_up(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """O P0 desta issue tem que ser legível na primeira linha, não caçado no plano."""
    main(["--observed", str(FLEET), "--config", str(DESIRED)])

    assert (
        "Política de Actions que cria e aprova PR (a esteira): ligada." in capsys.readouterr().out
    )


def test_apply_refuses_a_saved_snapshot_because_the_org_may_have_moved(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    code = main(["--apply", "--observed", str(FLEET), "--config", str(DESIRED)])

    assert code == 2
    assert "--apply não aceita --observed" in capsys.readouterr().err


def test_reading_the_live_org_warns_about_the_elevated_scope_before_calling_it(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    """O aviso sai antes da chamada: descobrir no meio da execução é tarde demais."""
    order: list[str] = []

    def note_call(*_args: object, **_kwargs: object) -> object:
        order.append("api")
        raise gh.GhError("HTTP 403")

    monkeypatch.setattr(gh, "api", note_call)

    code = main(["--config", str(DESIRED)])
    captured = capsys.readouterr()

    assert code == 1
    assert order == ["api"]
    assert "admin:org" in captured.err
    assert captured.err.index("admin:org") < captured.err.index("HTTP 403")


def test_reading_a_saved_snapshot_does_not_nag_about_a_scope_it_will_not_use(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    main(["--observed", str(FLEET), "--config", str(DESIRED)])

    assert "admin:org" not in capsys.readouterr().err


def test_an_empty_plan_from_an_undecided_config_does_not_claim_conformance(
    forbid_api: None, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    skeleton = tmp_path / "org.json"
    skeleton.write_text(json.dumps({"_nota": "nada decidido"}), encoding="utf-8")

    code = main(["--observed", str(FLEET), "--config", str(skeleton)])
    captured = capsys.readouterr()

    assert code == 0
    assert "Nada a fazer" in captured.out
    assert "NÃO quer dizer que a org está conforme" in captured.out
    assert "ainda sem decisão" in captured.err


def test_a_decided_config_with_nothing_to_do_does_say_the_org_converges(
    forbid_api: None, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    main(["--observed", str(converged_snapshot(tmp_path)), "--config", str(DESIRED)])

    assert "já converge com o desejado" in capsys.readouterr().out


def test_an_unreadable_security_dimension_is_an_error_not_a_fleet_out_of_standard(
    forbid_api: None, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    """Token sem escopo devolve o campo omitido; isso não pode virar deriva."""
    raw = json.loads(FLEET.read_text(encoding="utf-8"))
    del raw["org"]["two_factor_requirement_enabled"]
    path = tmp_path / "observed.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    code = main(["--observed", str(path), "--config", str(DESIRED)])

    assert code == 1
    assert "admin:org" in capsys.readouterr().err


def test_json_output_is_the_serialized_plan_and_nothing_else(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    main(["--observed", str(FLEET), "--config", str(DESIRED), "--json"])

    payload = json.loads(capsys.readouterr().out)

    assert len(payload["items"]) == 44
    assert {"action", "target", "reason", "payload", "hold"} == set(payload["items"][0])


def test_the_first_item_of_the_json_plan_is_the_org_itself(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    main(["--observed", str(FLEET), "--config", str(DESIRED), "--json"])

    payload = json.loads(capsys.readouterr().out)

    assert payload["items"][0]["target"] == "panlabs-tech"


def test_every_action_that_can_reach_the_applier_has_an_effect_registered():
    """Uma ação sem efeito só falharia na hora de aplicar, tarde demais."""
    emitted = {
        planner.SET_ACTIONS_PR_POLICY,
        planner.SET_ORG_SECURITY_DEFAULTS,
        planner.SET_TWO_FACTOR_REQUIREMENT,
        planner.SET_ORG_DESCRIPTION,
        planner.SET_PINNED_REPOS,
        planner.SET_SECRET_SCANNING,
        planner.SET_PUSH_PROTECTION,
        planner.SET_DEPENDABOT_ALERTS,
        planner.SET_DEPENDABOT_SECURITY_UPDATES,
        planner.SET_REPO_DESCRIPTION,
        planner.DECLARE_REPO_DESCRIPTION,
        planner.SET_REPO_TOPICS,
        planner.DECLARE_REPO_TOPICS,
        planner.SET_WIKI,
    }

    assert set(EFFECTS) == emitted - planner.ALWAYS_HELD


def test_no_always_held_action_has_an_effect_pretending_to_apply_it():
    """O que a API não expõe não ganha um efeito que falha na hora de agir."""
    assert set(EFFECTS) & planner.ALWAYS_HELD == set()


def test_the_held_items_are_shown_with_the_reason_they_will_not_be_applied(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """Retido aparece na leitura: sumir com ele faria o plano mentir sobre a deriva."""
    main(["--observed", str(FLEET), "--config", str(DESIRED)])

    out = capsys.readouterr().out

    assert "retido set-two-factor-requirement" in out
    assert "PATCH /orgs` não aceita two_factor_requirement_enabled" in out
    assert "retido(s): planejado(s) e não aplicado(s)." in out


# --- o resumo não conta como protegido o que ninguém mediu ---------------------


def test_the_summary_never_counts_an_unobservable_repo_as_protected(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """O disfarce mais barato de todos, e o mais fácil de não notar.

    `Unobservable` é um objeto, e objeto é truthy: um `if repo.secret_scanning`
    distraído conta como protegido justamente o repositório que ninguém conseguiu
    medir. A linha de resumo é a primeira coisa que o operador lê, e ela não pode
    ser a que mente.
    """
    code = main(["--observed", str(FLEET_WITH_PRIVATE), "--config", str(DESIRED)])
    out = capsys.readouterr().out

    assert code == 0
    assert "8 repo(s) na org viva" in out
    assert "7 com secret scanning e push protection" in out
    assert "1 sem observação" in out


def test_the_esteira_verdict_still_reaches_the_operator_with_a_private_repo_around(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """O invariante P0: é esta linha que o repo privado vinha apagando desde 25/07."""
    main(["--observed", str(FLEET_WITH_PRIVATE), "--config", str(DESIRED)])

    assert "a esteira): ligada" in capsys.readouterr().out
