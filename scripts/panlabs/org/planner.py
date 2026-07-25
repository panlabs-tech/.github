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

Duas dimensões não têm chamada de API que as aplique, e são planejadas como
**manuais**: a exigência de 2FA (que `PATCH /orgs` não aceita) e os repos
fixados no perfil (que o GitHub não expõe em REST nem em GraphQL). Elas ficam no
plano porque uma divergência que ninguém automatiza continua sendo divergência,
e some do plano quando o operador a resolver na web.
"""

from __future__ import annotations

import json
from typing import Any

from panlabs.org.config import Desired
from panlabs.org.model import Observed, OrgState, RepoState
from panlabs.plan import Plan, PlanItem

__all__ = [
    "DECLARE_REPO_DESCRIPTION",
    "DECLARE_REPO_TOPICS",
    "MANUAL_ACTIONS",
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

MANUAL_ACTIONS = frozenset(
    {
        SET_TWO_FACTOR_REQUIREMENT,
        SET_PINNED_REPOS,
        DECLARE_REPO_DESCRIPTION,
        DECLARE_REPO_TOPICS,
    }
)
"""As ações que nenhum efeito realiza: ou a API não as expõe, ou falta dado declarado."""

WEB_ONLY = "só pela web: a API do GitHub não expõe essa configuração"


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
            reason=_switch(
                "a política que permite ao Actions criar e aprovar PR",
                org.actions.can_approve_pull_requests,
                want,
                "é ela que sustenta a esteira worktree, commit, push, PR, merge no verde",
            ),
            payload={"body": org.actions.as_body(can_approve=want)},
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
            reason=_switch(
                "a exigência de 2FA na org",
                org.two_factor_required,
                want,
                "é ela que impede que a conta que administra tudo isso caia por senha. "
                f"{WEB_ONLY} (Settings > Authentication security): "
                "PATCH /orgs não aceita two_factor_requirement_enabled",
            ),
            payload={"two_factor_requirement_enabled": want},
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
                f"são {_show(list(want))}, nessa ordem: produtos antes de ferramental. "
                f"{WEB_ONLY} em REST nem em GraphQL"
            ),
            payload={"pinned_repos": list(want)},
        )
    ]


# --- cada repo ----------------------------------------------------------------


def _plan_repo(repo: RepoState, desired: Desired) -> list[PlanItem]:
    """Tudo que falta neste repo, com a dependência entre dimensões respeitada."""
    items: list[PlanItem] = []
    items.extend(_plan_secret_scanning(repo, desired))
    items.extend(_plan_push_protection(repo, desired))
    items.extend(_plan_dependabot_alerts(repo, desired))
    items.extend(_plan_dependabot_security_updates(repo, desired))
    items.extend(_plan_repo_description(repo, desired))
    items.extend(_plan_repo_topics(repo, desired))
    items.extend(_plan_wiki(repo, desired))
    return items


def _plan_secret_scanning(repo: RepoState, desired: Desired) -> list[PlanItem]:
    want = desired.secret_scanning
    if want is None or repo.secret_scanning == want:
        return []

    return [
        PlanItem(
            action=SET_SECRET_SCANNING,
            target=repo.name,
            reason=_switch(
                "secret scanning",
                repo.secret_scanning,
                want,
                "é ele que detecta segredo já commitado",
            ),
            payload={"body": _security_analysis("secret_scanning", want)},
        )
    ]


def _plan_push_protection(repo: RepoState, desired: Desired) -> list[PlanItem]:
    want = desired.push_protection
    if want is None or repo.push_protection == want:
        return []

    return [
        PlanItem(
            action=SET_PUSH_PROTECTION,
            target=repo.name,
            reason=_switch(
                "push protection",
                repo.push_protection,
                want,
                "é ela que impede um segredo de chegar ao remoto por descuido",
            ),
            payload={"body": _security_analysis("secret_scanning_push_protection", want)},
        )
    ]


def _plan_dependabot_alerts(repo: RepoState, desired: Desired) -> list[PlanItem]:
    want = desired.dependabot_alerts
    if want is None or repo.dependabot_alerts == want:
        return []

    return [
        PlanItem(
            action=SET_DEPENDABOT_ALERTS,
            target=repo.name,
            reason=_switch(
                "dependabot alerts",
                repo.dependabot_alerts,
                want,
                "é ele que transforma vulnerabilidade conhecida em alerta",
            ),
            payload={"method": _toggle_method(want)},
        )
    ]


def _plan_dependabot_security_updates(repo: RepoState, desired: Desired) -> list[PlanItem]:
    want = desired.dependabot_security_updates
    if want is None or repo.dependabot_security_updates == want:
        return []

    return [
        PlanItem(
            action=SET_DEPENDABOT_SECURITY_UPDATES,
            target=repo.name,
            reason=_switch(
                "dependabot security updates",
                repo.dependabot_security_updates,
                want,
                "é ele que transforma vulnerabilidade conhecida em PR sem ninguém pedir",
            ),
            payload={"method": _toggle_method(want)},
        )
    ]


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
                    "o repo não tem descrição na org e não tem texto declarado em "
                    "config/org.json; a listagem da org fica ilegível sem abrir o repo"
                ),
                payload={},
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
                    "o repo não tem topics e não tem eixo de stack declarado em "
                    "config/org.json; sem eles o agente não filtra a frota por tecnologia"
                ),
                payload={},
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
            reason=_switch(
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


def _switch(label: str, observed: bool, want: bool, why: str) -> str:
    """O motivo de uma dimensão liga-desliga: estado, alvo e o que está em jogo.

    A forma é a mesma que o planner do ruleset usa para divergência de campo,
    "observado X, desejado Y", e o "o que está em jogo" é dito de forma neutra ao
    sentido da mudança: o sentido vem do dado, e uma dimensão que amanhã for
    decidida ao contrário não pode fazer o motivo mentir.
    """
    estado = "ligado" if observed else "desligado"
    alvo = "ligado" if want else "desligado"
    return f"{label}: observado {estado}, desejado {alvo}; {why}"


def _security_analysis(key: str, enabled: bool) -> dict[str, Any]:
    return {"security_and_analysis": {key: {"status": "enabled" if enabled else "disabled"}}}


def _toggle_method(enabled: bool) -> str:
    """Ligar é PUT e desligar é DELETE: quem escolhe é o planner, não o efeito."""
    return "PUT" if enabled else "DELETE"


def _show(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)
