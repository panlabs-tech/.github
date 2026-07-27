"""A observação: um campo que a API não devolveu nunca vira um fato sobre a org.

Metade destas dimensões só é legível por quem administra a org, e o GitHub
responde a um token curto **omitindo** os campos, não negando a resposta. Se a
omissão virasse `False`, um token sem escopo diria "a esteira está desligada" e
"o wiki está conforme" com a mesma cara de quem observou. Cada campo ausente é
erro alto, e é isso que estes testes prendem.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from panlabs.org.model import RepoState
from panlabs.org.observe import build_observed, observed_to_dict
from panlabs.plan import Unobservable

FIXTURES = Path(__file__).parent / "fixtures"
FLEET = FIXTURES / "org-fleet-2026-07-27.json"

DOTFILES = "panlabs-tech/dotfiles"


def fleet_raw() -> dict[str, Any]:
    return json.loads(FLEET.read_text(encoding="utf-8"))


def test_the_live_snapshot_builds_the_state_the_planner_reads():
    observed = build_observed(fleet_raw())

    assert observed.org.login == "panlabs-tech"
    assert observed.org.actions.can_approve_pull_requests is True
    assert len(observed.repos) == 8


ADMIN_ONLY_ORG_FIELDS = ["two_factor_requirement_enabled"]
ADMIN_ONLY_REPO_FIELDS = [
    "security_and_analysis",
    "vulnerability_alerts",
    "automated_security_fixes",
]


@pytest.mark.parametrize("field", ADMIN_ONLY_ORG_FIELDS)
def test_an_org_field_only_an_admin_sees_is_an_error_when_absent(field: str):
    raw = fleet_raw()
    del raw["org"][field]

    with pytest.raises(ValueError, match="admin:org"):
        build_observed(raw)


@pytest.mark.parametrize("field", ADMIN_ONLY_REPO_FIELDS)
def test_a_repo_field_only_an_admin_sees_is_an_error_when_absent(field: str):
    raw = fleet_raw()
    del raw["repos"][0][field]

    with pytest.raises(ValueError, match="admin:org"):
        build_observed(raw)


def test_the_actions_policy_block_is_never_assumed():
    """Sem ela, "a esteira caiu" seria afirmação de quem não observou nada."""
    raw = fleet_raw()
    del raw["actions_workflow_permissions"]

    with pytest.raises(ValueError, match="can_approve_pull_request_reviews"):
        build_observed(raw)


def test_the_default_workflow_permission_is_read_from_the_org_not_invented():
    """Ela não é dimensão desta configuração, mas viaja no corpo que a aplica."""
    raw = fleet_raw()
    raw["actions_workflow_permissions"]["default_workflow_permissions"] = "write"

    assert build_observed(raw).org.actions.default_workflow_permissions == "write"


def test_an_absent_pin_list_is_an_error_instead_of_an_empty_showcase():
    raw = fleet_raw()
    del raw["pinned_repos"]

    with pytest.raises(ValueError, match="pinned_repos"):
        build_observed(raw)


def test_an_absent_wiki_flag_is_an_error_instead_of_silent_conformance():
    raw = fleet_raw()
    del raw["repos"][0]["has_wiki"]

    with pytest.raises(ValueError, match="has_wiki"):
        build_observed(raw)


def test_a_repo_without_description_or_topics_is_observed_as_such_not_rejected():
    """Ausência de vitrine é fato observável, e o planner é quem decide o que fazer."""
    raw = fleet_raw()
    repo = raw["repos"][0]
    repo["description"] = None
    repo["topics"] = []

    observed = build_observed(raw).repos[0]

    assert observed.description is None
    assert observed.topics == ()


# --- a dimensão que a plataforma não mostra ------------------------------------
#
# A frota ganhou repositório privado em 2026-07-25, e a fixture de 24 foi capturada
# antes dele. Foi por isso que 537 testes verdes deixaram passar um `AttributeError`
# na única rodada que serve de verificação do invariante P0.


def repo_named(name: str, raw: dict[str, Any] | None = None) -> RepoState:
    observed = build_observed(raw if raw is not None else fleet_raw())
    return next(repo for repo in observed.repos if repo.name == name)


def mutate(name: str, **fields: Any) -> dict[str, Any]:
    """O retrato com um repositório alterado, para exercitar o que ainda não aconteceu."""
    raw = fleet_raw()
    for entry in raw["repos"]:
        if entry["full_name"] == name:
            entry.update(fields)
    return raw


def test_the_snapshot_carries_the_private_repo_the_live_org_actually_has():
    observed = build_observed(fleet_raw())

    assert repo_named(DOTFILES).private is True
    assert [repo.name for repo in observed.repos if repo.private] == [DOTFILES]


def test_a_null_security_block_is_unobservable_instead_of_disabled():
    """`security_and_analysis: null` não diz que secret scanning está desligado.

    Diz que ninguém aqui consegue saber. Virar `False` faria o planner cobrar
    convergência de uma dimensão que a plataforma não oferece a este repositório,
    e o applier bateria na API tentando ligá-la.
    """
    dotfiles = repo_named(DOTFILES)

    assert isinstance(dotfiles.secret_scanning, Unobservable)
    assert isinstance(dotfiles.push_protection, Unobservable)


def test_the_unobservable_reason_names_the_repo_and_what_the_platform_did():
    """O motivo vira o `hold` do item retido, e é a única coisa que o operador lê."""
    reason = repo_named(DOTFILES).secret_scanning

    assert isinstance(reason, Unobservable)
    assert DOTFILES in reason.reason
    assert "security_and_analysis" in reason.reason


def test_the_dimensions_the_platform_did_answer_stay_plain_booleans():
    """Só as duas que moram no bloco nulo ficam sem observação, e nem uma a mais.

    Alerts e security updates têm endpoint próprio e responderam normalmente no
    repositório privado: retê-los junto seria inventar uma cegueira que não houve.
    """
    dotfiles = repo_named(DOTFILES)

    assert dotfiles.dependabot_alerts is False
    assert dotfiles.dependabot_security_updates is False
    assert dotfiles.wiki_enabled is False


def test_an_absent_security_key_is_still_a_loud_error_and_never_a_retention():
    """Ausente e nulo são causas diferentes, e só uma delas o operador conserta.

    A chave **ausente** é o sintoma de token sem `admin:org`, e continua sendo erro
    alto com a dica de como elevar o escopo. Retê-la em silêncio esconderia
    justamente a causa que tem conserto.
    """
    raw = mutate(DOTFILES)
    del raw["repos"][0]["security_and_analysis"]

    with pytest.raises(ValueError, match="admin:org"):
        build_observed(raw)


def test_a_security_block_that_answers_only_half_is_unobservable_in_the_other_half():
    """O bloco veio, e a dimensão dentro dele não: isso não é "desligado".

    É a mesma mentira que o bloco nulo produzia, um nível abaixo. O leitor antigo
    resolvia `(security.get(key) or {}).get("status") == "enabled"` como `False`,
    e um `False` aqui faria o planner cobrar convergência de uma dimensão sobre a
    qual a plataforma não disse nada.

    Nenhum repositório da frota responde assim hoje: os 7 públicos devolvem as 5
    chaves, e é justamente por isso que a causa provável seria a plataforma mudar
    de forma. É o momento em que um humano precisa olhar, e não o momento de
    planejar ligar secret scanning em toda a frota porque a chave mudou de nome.
    """
    raw = mutate(DOTFILES, security_and_analysis={"secret_scanning": {"status": "enabled"}})

    dotfiles = repo_named(DOTFILES, raw)

    assert dotfiles.secret_scanning is True
    assert isinstance(dotfiles.push_protection, Unobservable)


def test_the_half_answered_block_says_which_dimension_was_missing():
    """O motivo distingue as duas cegueiras: bloco ausente inteiro e chave que faltou.

    São causas diferentes com desfechos diferentes, e um texto só para as duas
    mandaria o operador procurar visibilidade de repositório quando o que mudou
    foi o nome de um campo.
    """
    reason = repo_named(
        DOTFILES,
        mutate(DOTFILES, security_and_analysis={"secret_scanning": {"status": "enabled"}}),
    ).push_protection

    assert isinstance(reason, Unobservable)
    assert "secret_scanning_push_protection" in reason.reason
    assert DOTFILES in reason.reason


def test_a_repo_that_becomes_public_leaves_the_retention_on_its_own():
    """A idempotência do conserto: nada aqui nomeia repositório nenhum.

    Quando a plataforma voltar a responder, a dimensão volta a ser booleana sozinha.
    Um conserto por lista de exceção precisaria de uma edição para sair.
    """
    raw = mutate(
        DOTFILES,
        private=False,
        security_and_analysis={
            "secret_scanning": {"status": "enabled"},
            "secret_scanning_push_protection": {"status": "disabled"},
        },
    )

    dotfiles = repo_named(DOTFILES, raw)

    assert dotfiles.secret_scanning is True
    assert dotfiles.push_protection is False


def test_the_serialized_state_shows_the_unobservable_dimension_instead_of_a_boolean():
    """O dump é o que o operador lê com `--show-observed`, antes de aprovar o plano.

    Um `false` ali diria que secret scanning está desligado no repositório privado,
    que é a afirmação que ninguém pode fazer. Um objeto no lugar de um booleano é
    visível de longe, e é serializável, que é mais do que a dataclass crua era.
    """
    dump = observed_to_dict(build_observed(fleet_raw()))
    dotfiles = next(entry for entry in dump["repos"] if entry["name"] == DOTFILES)

    assert json.dumps(dump)
    assert "security_and_analysis" in dotfiles["secret_scanning"]["unobservable"]
    assert "security_and_analysis" in dotfiles["push_protection"]["unobservable"]


def test_the_serialized_state_of_an_observed_dimension_stays_a_plain_boolean():
    dump = observed_to_dict(build_observed(fleet_raw()))
    meta = next(entry for entry in dump["repos"] if entry["name"] == "panlabs-tech/.github")

    assert meta["secret_scanning"] is True
