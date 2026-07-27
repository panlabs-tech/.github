"""O planner do checker: dado o estado observado, qual matriz de deriva sai dele.

    plan(observed) -> Plan

Sem `desired`: a anatomia não é dado configurável por spec de Org, é o
catálogo deste pacote. O checker é o caso mais puro do seam porque não tem
applier destrutivo -- "aplicar" aqui é só formatar e notificar.

Cada item de plano é uma linha da matriz que importa: uma deriva ou um erro de
observação. Um item avaliado e conforme não vira linha nenhuma, porque não é
uma ação pendente sobre nada -- é o mesmo "plano vazio" que já rege o resto do
repo: silêncio não afirma conformidade total, afirma que nada, dentro do que
foi avaliado, pediu atenção.
"""

from __future__ import annotations

from collections.abc import Sequence

from panlabs.checker.catalog import AnatomyItem
from panlabs.checker.model import Observed, RepoObserved
from panlabs.plan import Plan, PlanItem

__all__ = ["DRIFT_VERDICT", "ERROR_VERDICT", "plan"]

DRIFT_VERDICT = "deriva"
ERROR_VERDICT = "erro"

_NO_SCOPE_LABEL = "sem escopo (falha de observação)"


def plan(observed: Observed, catalog: Sequence[AnatomyItem]) -> Plan:
    """A matriz de deriva da frota inteira, em ordem estável de repo.

    O catálogo entra como segundo argumento pelo mesmo motivo que o `desired`
    entra nos outros planners: ele é construído a partir de dado versionado, e um
    default constante o faria ler arquivo em tempo de import.
    """
    items: list[PlanItem] = []
    for repo in observed.sorted_repos():
        items.extend(_plan_repo(repo, catalog))
    return Plan(tuple(items))


def _plan_repo(repo: RepoObserved, catalog: Sequence[AnatomyItem]) -> list[PlanItem]:
    if repo.error is not None:
        return [
            PlanItem(
                action="erro-observacao",
                target=repo.name,
                reason=repo.error,
                payload={"scope": _NO_SCOPE_LABEL, "verdict": ERROR_VERDICT},
            )
        ]

    items: list[PlanItem] = []
    for item in catalog:
        if not item.applies(repo):
            continue
        if item.satisfied(repo):
            continue
        items.append(
            PlanItem(
                action=item.id,
                target=repo.name,
                reason=item.motivo(repo),
                payload={"scope": item.scope.describe(), "verdict": DRIFT_VERDICT},
            )
        )
    return items
