"""O planner do ruleset. Puro, e o único lugar onde há decisão.

    plan(observed, desired) -> Plan

`desired` é dado, não observação — por isso entra como segundo argumento em vez
de dobrado dentro de `observed`. O seam continua sendo o mesmo: uma função pura
de estado para plano, e nada acima dela além da chamada real de API.

Uma dimensão ainda não decidida (`None`) não gera item nenhum. O script existe
antes dos valores que ele vai aplicar, e não pode inventá-los.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from panlabs.plan import Plan, PlanItem
from panlabs.ruleset.config import Desired
from panlabs.ruleset.model import Observed, RepoState, RulesetState

__all__ = [
    "CREATE_RULESET",
    "DELETE_CLASSIC_PROTECTION",
    "DELETE_RULESET",
    "UPDATE_RULESET",
    "diff_ruleset",
    "plan",
]

CREATE_RULESET = "create-ruleset"
UPDATE_RULESET = "update-ruleset"
DELETE_RULESET = "delete-ruleset"
DELETE_CLASSIC_PROTECTION = "delete-classic-protection"


def plan(observed: Observed, desired: Desired) -> Plan:
    """O plano de convergência da frota inteira, em ordem estável de repo."""
    items: list[PlanItem] = []
    for repo in observed.sorted_repos():
        items.extend(_plan_repo(repo, desired))
    return Plan(tuple(items))


def _plan_repo(repo: RepoState, desired: Desired) -> list[PlanItem]:
    """Tudo que falta neste repo — uma única leitura por branch, nunca duas.

    A ordem é deliberada: primeiro o ruleset converge, depois a proteção clássica
    é aposentada. Assim a branch nunca fica desprotegida entre um passo e outro.
    """
    items: list[PlanItem] = []
    if desired.ruleset is not None:
        items.extend(_plan_ruleset(repo, desired.ruleset))
    if desired.retire_classic_protection and repo.classic_protection is not None:
        items.append(
            PlanItem(
                action=DELETE_CLASSIC_PROTECTION,
                target=repo.name,
                reason=(
                    f"proteção clássica ativa em {repo.default_branch} "
                    f"({repo.classic_protection.describe()}); o ruleset passa a ser a única "
                    "fonte de verdade sobre a branch"
                ),
                payload={"branch": repo.default_branch},
            )
        )
    return items


def _plan_ruleset(repo: RepoState, desired_body: Mapping[str, Any]) -> list[PlanItem]:
    """O que falta para um único ruleset desejado governar a branch default.

    O ruleset a convergir é achado **pela branch que ele governa**, não pelo nome:
    procurar por nome faria um repo cujo ruleset se chama outra coisa ganhar um
    segundo ruleset sobre a mesma branch, que é exatamente a incoerência a evitar.
    """
    governing = repo.rulesets_governing_default_branch()

    if not governing:
        return [
            PlanItem(
                action=CREATE_RULESET,
                target=repo.name,
                reason=(
                    f"nenhum ruleset governa a branch {repo.default_branch}"
                    + (
                        f" (existem {len(repo.rulesets)} ruleset(s) fora dessa branch)"
                        if repo.rulesets
                        else ""
                    )
                ),
                payload={"body": dict(desired_body)},
            )
        ]

    # Qual dos concorrentes sobrevive é indiferente ao estado final: o sobrevivente
    # é sobrescrito com o corpo desejado de qualquer jeito. O critério é o mais
    # antigo só para que o plano seja estável entre duas leituras.
    primary, *extras = governing
    items: list[PlanItem] = []

    divergences = diff_ruleset(primary, desired_body)
    if divergences:
        items.append(
            PlanItem(
                action=UPDATE_RULESET,
                target=repo.name,
                reason=(
                    f'ruleset "{primary.name}" diverge do desejado em '
                    f"{len(divergences)} ponto(s): " + "; ".join(divergences)
                ),
                payload={"ruleset_id": primary.id, "body": dict(desired_body)},
            )
        )

    for extra in extras:
        items.append(
            PlanItem(
                action=DELETE_RULESET,
                target=repo.name,
                reason=(
                    f'o ruleset "{extra.name}" também governa {repo.default_branch}, além de '
                    f'"{primary.name}"; duas fontes de verdade sobre a mesma branch'
                ),
                payload={"ruleset_id": extra.id},
            )
        )

    return items


# --- comparação ---------------------------------------------------------------
#
# O desejado é comparado como **subconjunto declarado**: só os campos escritos no
# dado são cobrados. A API preenche defaults que não foram enviados, e cobrar o
# que não se declarou faria o plano nunca esvaziar.
#
# As **regras**, ao contrário, são comparadas como conjunto exato pelo seu `type`:
# uma regra que ninguém pediu é deriva, e some do plano só quando sair do repo.


def diff_ruleset(observed: RulesetState, desired_body: Mapping[str, Any]) -> tuple[str, ...]:
    """As divergências entre o ruleset observado e o desejado, em pt-BR."""
    scalars = {k: v for k, v in desired_body.items() if k != "rules"}
    divergences = _compare("", scalars, observed.comparable())
    divergences += _compare_rules(desired_body.get("rules") or (), observed.rules)
    return tuple(divergences)


def _compare(path: str, desired: Any, observed: Any) -> list[str]:
    if isinstance(desired, Mapping):
        if not isinstance(observed, Mapping):
            return [f"{path}: observado {_show(observed)}, desejado um objeto"]
        out: list[str] = []
        for key in desired:
            child = f"{path}.{key}" if path else key
            if key not in observed:
                out.append(f"{child}: ausente, desejado {_show(desired[key])}")
            else:
                out += _compare(child, desired[key], observed[key])
        return out

    if isinstance(desired, list | tuple):
        if not isinstance(observed, list | tuple):
            return [f"{path}: observado {_show(observed)}, desejado uma lista"]
        if _bag(desired) != _bag(observed):
            return [f"{path}: observado {_show(observed)}, desejado {_show(desired)}"]
        return []

    if desired != observed:
        return [f"{path}: observado {_show(observed)}, desejado {_show(desired)}"]
    return []


def _compare_rules(
    desired_rules: Sequence[Mapping[str, Any]],
    observed_rules: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    desired_by_type = {rule["type"]: rule.get("parameters") or {} for rule in desired_rules}

    out: list[str] = []
    for rule_type in sorted(set(desired_by_type) - set(observed_rules)):
        out.append(f"regra {rule_type}: ausente")
    for rule_type in sorted(set(observed_rules) - set(desired_by_type)):
        out.append(f"regra {rule_type}: presente e não desejada")
    for rule_type in sorted(set(desired_by_type) & set(observed_rules)):
        out += _compare(f"regra {rule_type}", desired_by_type[rule_type], observed_rules[rule_type])
    return out


def _bag(values: Sequence[Any]) -> list[str]:
    """Uma lista comparável sem ordem — ordem de contexto ou de ator não é semântica."""
    return sorted(json.dumps(v, sort_keys=True, ensure_ascii=False) for v in values)


def _show(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)
