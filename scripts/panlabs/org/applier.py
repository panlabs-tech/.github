"""Os efeitos de org e repo: uma chamada de API por ação, e nada mais.

Não há ramificação de decisão aqui, e não pode haver. Cada efeito recebe um item
cujo `payload` o planner já montou por inteiro: o corpo enviado à API é dado
carregado pelo plano, e até o método HTTP das dimensões que ligam com `PUT` e
desligam com `DELETE` vem escrito no item.

As ações manuais (`planner.MANUAL_ACTIONS`) não têm efeito registrado, de
propósito: elas não são aplicáveis por API nenhuma, e inventar um efeito que
falha na hora de agir seria pior do que dizê-lo no plano.
"""

from __future__ import annotations

from panlabs import gh
from panlabs.org.planner import (
    SET_ACTIONS_PR_POLICY,
    SET_DEPENDABOT_ALERTS,
    SET_DEPENDABOT_SECURITY_UPDATES,
    SET_ORG_DESCRIPTION,
    SET_ORG_SECURITY_DEFAULTS,
    SET_PUSH_PROTECTION,
    SET_REPO_DESCRIPTION,
    SET_REPO_TOPICS,
    SET_SECRET_SCANNING,
    SET_WIKI,
)
from panlabs.plan import Effect, PlanItem

__all__ = ["EFFECTS"]


def _set_actions_pr_policy(item: PlanItem) -> None:
    gh.api(
        f"orgs/{item.target}/actions/permissions/workflow",
        method="PUT",
        body=item.payload["body"],
    )


def _patch_org(item: PlanItem) -> None:
    gh.api(f"orgs/{item.target}", method="PATCH", body=item.payload["body"])


def _patch_repo(item: PlanItem) -> None:
    gh.api(f"repos/{item.target}", method="PATCH", body=item.payload["body"])


def _set_topics(item: PlanItem) -> None:
    gh.api(f"repos/{item.target}/topics", method="PUT", body=item.payload["body"])


def _set_dependabot_alerts(item: PlanItem) -> None:
    gh.api(f"repos/{item.target}/vulnerability-alerts", method=item.payload["method"])


def _set_dependabot_security_updates(item: PlanItem) -> None:
    gh.api(f"repos/{item.target}/automated-security-fixes", method=item.payload["method"])


EFFECTS: dict[str, Effect] = {
    SET_ACTIONS_PR_POLICY: _set_actions_pr_policy,
    SET_ORG_SECURITY_DEFAULTS: _patch_org,
    SET_ORG_DESCRIPTION: _patch_org,
    SET_SECRET_SCANNING: _patch_repo,
    SET_PUSH_PROTECTION: _patch_repo,
    SET_DEPENDABOT_ALERTS: _set_dependabot_alerts,
    SET_DEPENDABOT_SECURITY_UPDATES: _set_dependabot_security_updates,
    SET_REPO_DESCRIPTION: _patch_repo,
    SET_REPO_TOPICS: _set_topics,
    SET_WIKI: _patch_repo,
}
