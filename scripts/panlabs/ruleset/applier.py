"""Os efeitos do ruleset: uma chamada de API por ação, e nada mais.

Não há ramificação de decisão aqui, e não pode haver. Cada efeito recebe um item
cujo `payload` o planner já montou por inteiro, o corpo enviado à API é dado
carregado pelo plano, não algo calculado na hora de agir.

Se algum dia um efeito precisar de um `if`, a decisão vazou para dentro dele, e o
conserto é movê-la para o planner, não testar o applier.
"""

from __future__ import annotations

from panlabs import gh
from panlabs.plan import Effect, PlanItem
from panlabs.ruleset.planner import (
    CREATE_RULESET,
    DELETE_CLASSIC_PROTECTION,
    DELETE_RULESET,
    UPDATE_REPO_SETTINGS,
    UPDATE_RULESET,
)

__all__ = ["EFFECTS"]


def _create_ruleset(item: PlanItem) -> None:
    gh.api(f"repos/{item.target}/rulesets", method="POST", body=item.payload["body"])


def _update_ruleset(item: PlanItem) -> None:
    gh.api(
        f"repos/{item.target}/rulesets/{item.payload['ruleset_id']}",
        method="PUT",
        body=item.payload["body"],
    )


def _delete_ruleset(item: PlanItem) -> None:
    gh.api(f"repos/{item.target}/rulesets/{item.payload['ruleset_id']}", method="DELETE")


def _delete_classic_protection(item: PlanItem) -> None:
    gh.api(
        f"repos/{item.target}/branches/{item.payload['branch']}/protection",
        method="DELETE",
    )


def _update_repo_settings(item: PlanItem) -> None:
    gh.api(f"repos/{item.target}", method="PATCH", body=item.payload["settings"])


EFFECTS: dict[str, Effect] = {
    CREATE_RULESET: _create_ruleset,
    UPDATE_RULESET: _update_ruleset,
    DELETE_RULESET: _delete_ruleset,
    DELETE_CLASSIC_PROTECTION: _delete_classic_protection,
    UPDATE_REPO_SETTINGS: _update_repo_settings,
}
