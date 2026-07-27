"""O planner do checker: dado o estado observado, qual matriz de deriva sai dele.

    plan(observed, desired) -> Plan

O catálogo de itens é código, não configuração: um item é um predicado, e a
anatomia não é dado que uma spec de Org negocia. O `desired` que entra aqui é
outra coisa, e é pequena: o punhado de dimensões em que o item existe e o
**valor** com que ele compara ainda é decisão (a licença uniforme, os majors de
runtime convergidos, a exceção de wiki). Uma dimensão não decidida não é avaliada,
que é diferente de decidida-como-vazia e o oposto de conforme.

O checker é o caso mais puro do seam porque não tem applier destrutivo --
"aplicar" aqui é só formatar e notificar.

Cada item de plano é uma linha da matriz que importa: uma deriva ou um erro de
observação. Um item avaliado e conforme não vira linha nenhuma, porque não é
uma ação pendente sobre nada -- é o mesmo "plano vazio" que já rege o resto do
repo: silêncio não afirma conformidade total, afirma que nada, dentro do que
foi avaliado, pediu atenção.
"""

from __future__ import annotations

from panlabs.checker.catalog import DEFAULT_CATALOG, AnatomyItem
from panlabs.checker.desired import Desired
from panlabs.checker.model import Observed, RepoObserved
from panlabs.plan import Plan, PlanItem

__all__ = ["DRIFT_VERDICT", "ERROR_VERDICT", "plan"]

DRIFT_VERDICT = "deriva"
ERROR_VERDICT = "erro"

_NO_SCOPE_LABEL = "sem escopo (falha de observação)"

NOTHING_DECIDED = Desired()
"""O default de `desired`: nada decidido, e nada conveniente.

Os itens que comparam contra valor decidido simplesmente não são avaliados contra
este, e nenhum deles vira falso verde. Um default com valores dentro seria o
checker inventando decisão que ninguém tomou.
"""


def plan(
    observed: Observed,
    desired: Desired = NOTHING_DECIDED,
    catalog: tuple[AnatomyItem, ...] = DEFAULT_CATALOG,
) -> Plan:
    """A matriz de deriva da frota inteira, em ordem estável de repo."""
    items: list[PlanItem] = []
    for repo in observed.sorted_repos():
        items.extend(_plan_repo(repo, desired, catalog))
    return Plan(tuple(items))


def _plan_repo(
    repo: RepoObserved, desired: Desired, catalog: tuple[AnatomyItem, ...]
) -> list[PlanItem]:
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
        if not item.applies(repo, desired):
            continue
        if item.satisfied(repo, desired):
            continue
        items.append(
            PlanItem(
                action=item.id,
                target=repo.name,
                reason=item.motivo(repo, desired),
                payload={"scope": item.scope.describe(), "verdict": DRIFT_VERDICT},
            )
        )
    return items
