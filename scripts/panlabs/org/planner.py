"""O planner de org e repo. Puro, e o único lugar onde há decisão.

    plan(observed, desired) -> Plan

Cada dimensão diverge **sozinha**: um repo com só o wiki fora do padrão produz
um item de wiki, e nada mais. É isso que faz do plano um relatório legível e do
comando uma verificação de invariante, não só um aplicador.

A ordem é deliberada em três níveis:

1. A política de Actions que cria e aprova PR vem **primeiro**, antes de qualquer
   outra coisa: é ela que sustenta a esteira, e a esteira parada é o único item
   cujo custo corre agora.
2. Dentro de um repo, uma dimensão que depende de outra vem depois dela: push
   protection depois de secret scanning, security updates depois dos alerts.
3. Os repos saem em ordem de nome, para que duas leituras produzam o mesmo plano.

Duas dimensões não têm chamada de API que as aplique, e nascem **retidas** pelo
`hold` do seam: a exigência de 2FA (que `PATCH /orgs` não aceita) e os repos
fixados no perfil (que o GitHub não expõe em REST nem em GraphQL). Retidas
também nascem as duas que dependem de dado que ninguém declarou: a descrição e
os topics de um repo que não está em `config/org.json`.

Retido é diferente de ausente: o item aparece na leitura, com o motivo da
divergência e o motivo da retenção, e o `apply` não o realiza. Some do plano
quando o operador resolver, na web ou no dado. Esconder essas quatro faria o
plano mentir sobre a deriva; inventar um efeito para elas faria o `apply` falhar
na hora de agir.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from panlabs.org.config import Desired
from panlabs.org.model import ActionsPolicy, Observed, OrgState, RepoState
from panlabs.plan import Plan, PlanItem

__all__ = [
    "ALWAYS_HELD",
    "DECLARE_REPO_DESCRIPTION",
    "DECLARE_REPO_TOPICS",
    "SET_ACTIONS_PR_POLICY",
    "SET_DEPENDABOT_ALERTS",
    "SET_DEPENDABOT_SECURITY_UPDATES",
    "SET_ORG_DESCRIPTION",
    "SET_ORG_SECURITY_DEFAULTS",
    "SET_PINNED_REPOS",
    "SET_PUSH_PROTECTION",
    "SET_REPO_DESCRIPTION",
    "SET_REPO_TOPICS",
    "SET_SECRET_SCANNING",
    "SET_TWO_FACTOR_REQUIREMENT",
    "SET_WIKI",
    "plan",
]

SET_ACTIONS_PR_POLICY = "set-actions-pr-policy"
SET_ORG_SECURITY_DEFAULTS = "set-org-security-defaults"
SET_TWO_FACTOR_REQUIREMENT = "set-two-factor-requirement"
SET_ORG_DESCRIPTION = "set-org-description"
SET_PINNED_REPOS = "set-pinned-repos"

SET_SECRET_SCANNING = "set-secret-scanning"
SET_PUSH_PROTECTION = "set-push-protection"
SET_DEPENDABOT_ALERTS = "set-dependabot-alerts"
SET_DEPENDABOT_SECURITY_UPDATES = "set-dependabot-security-updates"
SET_REPO_DESCRIPTION = "set-repo-description"
DECLARE_REPO_DESCRIPTION = "declare-repo-description"
SET_REPO_TOPICS = "set-repo-topics"
DECLARE_REPO_TOPICS = "declare-repo-topics"
SET_WIKI = "set-wiki"

HOLD_TWO_FACTOR = (
    "`PATCH /orgs` não aceita two_factor_requirement_enabled; a exigência de 2FA "
    "só se liga pela web, em Settings > Authentication security"
)
HOLD_PINS = (
    "o GitHub não expõe mutação de pinned items, nem em REST nem em GraphQL; "
    "os pins só se mudam pela web, no perfil da org"
)
HOLD_UNDECLARED_DESCRIPTION = (
    "não há texto declarado em config/org.json, e inventar a descrição de um repo "
    "não é trabalho de script"
)
HOLD_UNDECLARED_TOPICS = (
    "não há eixo de stack declarado em config/org.json, e escolher a stack de um "
    "repo não é trabalho de script"
)

ALWAYS_HELD = frozenset(
    {
        SET_TWO_FACTOR_REQUIREMENT,
        SET_PINNED_REPOS,
        DECLARE_REPO_DESCRIPTION,
        DECLARE_REPO_TOPICS,
    }
)
"""As ações que nascem retidas em toda circunstância, e por isso não têm efeito.

Reter aqui não é "hoje não dá", como no retrofit de CI do ruleset: é "não existe
chamada que faça isso". A distinção fica no texto do `hold` de cada item; o que
o seam garante é o mesmo nos dois casos, o `apply` não as executa.
"""


def plan(observed: Observed, desired: Desired) -> Plan:
    """O plano de convergência da org e da frota, em ordem estável."""
    items = _plan_org(observed.org, desired)
    for repo in observed.sorted_repos():
        items.extend(_plan_repo(repo, desired))
    return Plan(tuple(items))


# --- a org --------------------------------------------------------------------


def _plan_org(org: OrgState, desired: Desired) -> list[PlanItem]:
    items: list[PlanItem] = []
    items.extend(_plan_actions_policy(org, desired))
    items.extend(_plan_security_defaults(org, desired))
    items.extend(_plan_two_factor(org, desired))
    items.extend(_plan_org_description(org, desired))
    items.extend(_plan_pins(org, desired))
    return items


def _plan_actions_policy(org: OrgState, desired: Desired) -> list[PlanItem]:
    """P0: o botão desligado que quebrou a esteira, e o primeiro item do plano."""
    want = desired.actions_can_approve_pull_requests
    if want is None or org.actions.can_approve_pull_requests == want:
        return []

    return [
        PlanItem(
            action=SET_ACTIONS_PR_POLICY,
            target=org.login,
            reason=_toggle_reason(
                "a política que permite ao Actions criar e aprovar PR",
                org.actions.can_approve_pull_requests,
                want,
                "é ela que sustenta a esteira worktree, commit, push, PR, merge no verde",
            ),
            payload={"body": _actions_body(org.actions, can_approve=want)},
        )
    ]


def _plan_security_defaults(org: OrgState, desired: Desired) -> list[PlanItem]:
    """Uma dimensão só, com o motivo nomeando cada chave divergente."""
    want = desired.new_repo_security_defaults
    if want is None:
        return []

    divergences = [
        f"{key}: observado {_show(org.security_defaults.get(key, 'ausente'))}, "
        f"desejado {_show(value)}"
        for key, value in sorted(want.items())
        if org.security_defaults.get(key) != value
    ]
    if not divergences:
        return []

    return [
        PlanItem(
            action=SET_ORG_SECURITY_DEFAULTS,
            target=org.login,
            reason=(
                f"os defaults de segurança para repositório novo divergem em "
                f"{len(divergences)} chave(s): " + "; ".join(divergences) + "; "
                "sem eles, um repo criado amanhã nasce desprotegido"
            ),
            payload={"body": dict(want)},
        )
    ]


def _plan_two_factor(org: OrgState, desired: Desired) -> list[PlanItem]:
    want = desired.two_factor_requirement
    if want is None or org.two_factor_required == want:
        return []

    return [
        PlanItem(
            action=SET_TWO_FACTOR_REQUIREMENT,
            target=org.login,
            reason=_toggle_reason(
                "a exigência de 2FA na org",
                org.two_factor_required,
                want,
                "é ela que impede que a conta que administra tudo isso caia por senha",
            ),
            hold=HOLD_TWO_FACTOR,
        )
    ]


def _plan_org_description(org: OrgState, desired: Desired) -> list[PlanItem]:
    want = desired.org_description
    if want is None or org.description == want:
        return []

    return [
        PlanItem(
            action=SET_ORG_DESCRIPTION,
            target=org.login,
            reason=(
                f"a descrição da org é {_show(org.description)}, e a desejada é {_show(want)}; "
                "a descrição é a promessa que a org faz a quem chega de fora"
            ),
            payload={"body": {"description": want}},
        )
    ]


def _plan_pins(org: OrgState, desired: Desired) -> list[PlanItem]:
    """Os pins comparam **em ordem**: a ordem é a vitrine, não detalhe de leitura."""
    want = desired.pinned_repos
    if want is None or list(org.pinned_repos) == list(want):
        return []

    return [
        PlanItem(
            action=SET_PINNED_REPOS,
            target=org.login,
            reason=(
                f"os repos fixados no perfil são {_show(list(org.pinned_repos))}, e os desejados "
                f"são {_show(list(want))}, nessa ordem: produtos antes de ferramental"
            ),
            hold=HOLD_PINS,
        )
    ]


# --- cada repo ----------------------------------------------------------------


@dataclass(frozen=True)
class Toggle:
    """Uma dimensão liga-desliga de repositório, como dado em vez de como código.

    Quatro dimensões desta configuração têm exatamente a mesma forma: ler um
    booleano observado, comparar com um booleano desejado, montar um corpo. O
    que muda entre elas é constante, e constante é tabela. É a mesma escolha do
    catálogo do checker (`panlabs.checker.catalog`), pelo mesmo motivo: uma
    quinta dimensão deve ser uma linha, não uma quinta cópia do mesmo `if`.
    """

    action: str
    label: str
    why: str
    """O que essa dimensão protege, dito sem depender do sentido da mudança."""
    observed: Callable[[RepoState], bool]
    wanted: Callable[[Desired], bool | None]
    payload: Callable[[bool], Mapping[str, Any]]


REPO_TOGGLES: tuple[Toggle, ...] = (
    # A ordem é a de aplicação, e ela importa: push protection depende de secret
    # scanning, e os security updates dependem dos alerts. Aplicar na ordem
    # inversa deixaria o segundo passo sem o alicerce que a API exige.
    Toggle(
        action=SET_SECRET_SCANNING,
        label="secret scanning",
        why="é ele que detecta segredo já commitado",
        observed=lambda repo: repo.secret_scanning,
        wanted=lambda desired: desired.secret_scanning,
        payload=lambda enabled: {"body": _security_analysis("secret_scanning", enabled)},
    ),
    Toggle(
        action=SET_PUSH_PROTECTION,
        label="push protection",
        why="é ela que impede um segredo de chegar ao remoto por descuido",
        observed=lambda repo: repo.push_protection,
        wanted=lambda desired: desired.push_protection,
        payload=lambda enabled: {
            "body": _security_analysis("secret_scanning_push_protection", enabled)
        },
    ),
    Toggle(
        action=SET_DEPENDABOT_ALERTS,
        label="dependabot alerts",
        why="é ele que transforma vulnerabilidade conhecida em alerta",
        observed=lambda repo: repo.dependabot_alerts,
        wanted=lambda desired: desired.dependabot_alerts,
        payload=lambda enabled: {"method": _toggle_method(enabled)},
    ),
    Toggle(
        action=SET_DEPENDABOT_SECURITY_UPDATES,
        label="dependabot security updates",
        why="é ele que transforma vulnerabilidade conhecida em PR sem ninguém pedir",
        observed=lambda repo: repo.dependabot_security_updates,
        wanted=lambda desired: desired.dependabot_security_updates,
        payload=lambda enabled: {"method": _toggle_method(enabled)},
    ),
)


def _plan_repo(repo: RepoState, desired: Desired) -> list[PlanItem]:
    """Tudo que falta neste repo, com a dependência entre dimensões respeitada."""
    items: list[PlanItem] = []
    items.extend(_plan_toggles(repo, desired))
    items.extend(_plan_repo_description(repo, desired))
    items.extend(_plan_repo_topics(repo, desired))
    items.extend(_plan_wiki(repo, desired))
    return items


def _plan_toggles(repo: RepoState, desired: Desired) -> list[PlanItem]:
    """As dimensões liga-desliga do repo, na ordem em que podem ser aplicadas."""
    items: list[PlanItem] = []
    for toggle in REPO_TOGGLES:
        want = toggle.wanted(desired)
        if want is None:
            continue
        observed = toggle.observed(repo)
        if observed == want:
            continue
        items.append(
            PlanItem(
                action=toggle.action,
                target=repo.name,
                reason=_toggle_reason(toggle.label, observed, want, toggle.why),
                payload=toggle.payload(want),
            )
        )
    return items


def _plan_repo_description(repo: RepoState, desired: Desired) -> list[PlanItem]:
    """O dado governa o texto onde ele existe; onde não existe, cobra que exista.

    Inventar a descrição de um repo não é trabalho de script: por isso o repo sem
    texto declarado e sem descrição própria vira item **manual**, endereçado ao
    dado, e não uma chamada de API com um texto que ninguém decidiu.
    """
    declared = desired.repo_descriptions
    if declared is None:
        return []

    want = declared.get(repo.name)
    if want is None:
        if repo.description:
            return []
        return [
            PlanItem(
                action=DECLARE_REPO_DESCRIPTION,
                target=repo.name,
                reason=(
                    "o repo não tem descrição na org; a listagem da org fica ilegível "
                    "sem abrir repo por repo"
                ),
                hold=HOLD_UNDECLARED_DESCRIPTION,
            )
        ]

    if repo.description == want:
        return []

    return [
        PlanItem(
            action=SET_REPO_DESCRIPTION,
            target=repo.name,
            reason=(
                f"a descrição do repo é {_show(repo.description)}, e a declarada em "
                f"config/org.json é {_show(want)}"
            ),
            payload={"body": {"description": want}},
        )
    ]


def _plan_repo_topics(repo: RepoState, desired: Desired) -> list[PlanItem]:
    """Topics comparam como **conjunto**: a API os devolve reordenados."""
    declared = desired.repo_topics
    if declared is None:
        return []

    want = declared.get(repo.name)
    if want is None:
        if repo.topics:
            return []
        return [
            PlanItem(
                action=DECLARE_REPO_TOPICS,
                target=repo.name,
                reason=(
                    "o repo não tem topics; sem eles o agente não filtra a frota por tecnologia"
                ),
                hold=HOLD_UNDECLARED_TOPICS,
            )
        ]

    observed_set, desired_set = set(repo.topics), set(want)
    if observed_set == desired_set:
        return []

    extra = sorted(observed_set - desired_set)
    missing = sorted(desired_set - observed_set)
    divergences: list[str] = []
    if extra:
        divergences.append(f"sobra(m) {', '.join(extra)}, fora do eixo de stack")
    if missing:
        divergences.append(f"falta(m) {', '.join(missing)}")

    return [
        PlanItem(
            action=SET_REPO_TOPICS,
            target=repo.name,
            reason="os topics do repo divergem do eixo declarado: " + "; ".join(divergences),
            payload={"body": {"names": list(want)}},
        )
    ]


def _plan_wiki(repo: RepoState, desired: Desired) -> list[PlanItem]:
    """Um repo declarado como exceção não é avaliado, e não aparece no plano.

    A exceção é dado, não condição embutida: é o que permite ao repo cujo wiki é
    gerado por automação de release conviver com a regra sem virar `if`.
    """
    if desired.wiki is None or repo.name in desired.wiki_exceptions():
        return []

    want = bool(desired.wiki["enabled"])
    if repo.wiki_enabled == want:
        return []

    return [
        PlanItem(
            action=SET_WIKI,
            target=repo.name,
            reason=_toggle_reason(
                "wiki",
                repo.wiki_enabled,
                want,
                "wiki que ninguém usa é superfície vazia que ninguém mantém, e o repo que "
                "o usa entra como exceção declarada em config/org.json",
            ),
            payload={"body": {"has_wiki": want}},
        )
    ]


# --- vocabulário compartilhado ------------------------------------------------


def _toggle_reason(label: str, observed: bool, want: bool, why: str) -> str:
    """O motivo de uma dimensão liga-desliga: estado, alvo e o que está em jogo.

    A forma é a mesma que o planner do ruleset usa para divergência de campo,
    "observado X, desejado Y", e o "o que está em jogo" é dito de forma neutra ao
    sentido da mudança: o sentido vem do dado, e uma dimensão que amanhã for
    decidida ao contrário não pode fazer o motivo mentir.
    """
    estado = "ligado" if observed else "desligado"
    alvo = "ligado" if want else "desligado"
    return f"{label}: observado {estado}, desejado {alvo}; {why}"


def _actions_body(observed: ActionsPolicy, *, can_approve: bool) -> dict[str, Any]:
    """O corpo do PUT da política de Actions, com o que ele não governa preservado.

    Os dois campos viajam juntos porque a API os trata como um par: enviar só um
    devolveria o outro ao default, e a permissão default do token de workflow não
    é dimensão desta configuração, é estado observado a preservar.
    """
    return {
        "default_workflow_permissions": observed.default_workflow_permissions,
        "can_approve_pull_request_reviews": can_approve,
    }


def _security_analysis(key: str, enabled: bool) -> dict[str, Any]:
    return {"security_and_analysis": {key: {"status": "enabled" if enabled else "disabled"}}}


def _toggle_method(enabled: bool) -> str:
    """Ligar é PUT e desligar é DELETE: quem escolhe é o planner, não o efeito."""
    return "PUT" if enabled else "DELETE"


def _show(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)
