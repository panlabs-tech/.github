"""O planner do ruleset. Puro, e o único lugar onde há decisão.

    plan(observed, desired) -> Plan

`desired` é dado, não observação: por isso entra como segundo argumento em vez
de dobrado dentro de `observed`. O seam continua sendo o mesmo: uma função pura
de estado para plano, e nada acima dela além da chamada real de API.

Uma dimensão ainda não decidida (`None`) não gera item nenhum. O script existe
antes dos valores que ele vai aplicar, e não pode inventá-los.

Um repo cuja CI ainda não publica os nomes fixos de check entra no plano **retido**:
a divergência é mostrada, e não é aplicada. Reter é decisão, e por isso mora aqui.

Um repo cuja proteção a plataforma **recusou a mostrar** também entra retido, e
por um motivo diferente. Lá o observador viu tudo e o repo é que não está pronto;
aqui não há observação nenhuma sobre a qual decidir. Por isso o item que ele
produz não é uma convergência adiada, e sim `observe-protection`: o pendente é a
leitura, não a aplicação. Nenhum `create-ruleset` sai daqui, porque mandar criar
um ruleset que já pode existir é uma afirmação sobre a branch que ninguém mediu.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from typing import Any

from panlabs.plan import Plan, PlanItem
from panlabs.ruleset.config import Desired
from panlabs.ruleset.model import Observed, RepoState, RulesetState

__all__ = [
    "CREATE_RULESET",
    "DELETE_CLASSIC_PROTECTION",
    "DELETE_RULESET",
    "OBSERVE_PROTECTION",
    "UPDATE_REPO_SETTINGS",
    "UPDATE_RULESET",
    "diff_ruleset",
    "plan",
]

CREATE_RULESET = "create-ruleset"
UPDATE_RULESET = "update-ruleset"
DELETE_RULESET = "delete-ruleset"
DELETE_CLASSIC_PROTECTION = "delete-classic-protection"
UPDATE_REPO_SETTINGS = "update-repo-settings"

OBSERVE_PROTECTION = "observe-protection"
"""O que falta neste repo é a **leitura**, e não a aplicação.

As outras ações nomeiam o que o applier faria. Esta nomeia o que ninguém
conseguiu fazer, e por isso nasce sempre retida e não tem efeito registrado:
não existe chamada de API que torne um repositório observável. Reusar
`create-ruleset` aqui teria sido mais barato e teria mentido, porque afirmaria
que nenhum ruleset governa a branch, que é exatamente o que ninguém mediu.
"""


def plan(observed: Observed, desired: Desired, *, retrofitted: Collection[str] = ()) -> Plan:
    """O plano de convergência da frota inteira, em ordem estável de repo.

    `retrofitted` nomeia os repos cuja CI o operador afirma já publicar os nomes
    fixos de check, e é o que `--only` significa: nomear um repo é assumir essa
    responsabilidade por ele. Para os nomeados, o portão de checks não vale.
    """
    items: list[PlanItem] = []
    for repo in observed.sorted_repos():
        items.extend(_plan_repo(repo, desired, hold=_hold(repo, desired, retrofitted)))
    return Plan(tuple(items))


def _plan_repo(repo: RepoState, desired: Desired, *, hold: str) -> list[PlanItem]:
    """Tudo que falta neste repo: uma única leitura por branch, nunca duas.

    A ordem é deliberada e vale como sequência de aplicação. Primeiro a
    configuração do repositório, porque é ela que restringe o merge a squash:
    subir a exigência de assinatura antes disso deixaria o commit local do agente,
    que não é assinado, aterrissar na branch por merge ou rebase e reprovar a
    regra recém-criada. Depois o ruleset. Por último a proteção clássica é
    aposentada, para que a branch nunca fique desprotegida entre um passo e outro.

    O `hold` é do repo inteiro, não de um item: metade da convergência é pior que
    nenhuma. Aposentar a clássica sem subir o ruleset deixaria a branch nua, e
    restringir o merge sem exigir assinatura mudaria o fluxo sem entregar a garantia.
    Nem mesmo o auto-merge escapa disso: ele só faz efeito quando existe um required
    check segurando o PR, então ligá-lo num repo cujo ruleset ficou para depois não
    entregaria nada, só mexeria na configuração de um repo que ninguém convergiu.
    """
    items: list[PlanItem] = []
    if desired.repo_settings is not None:
        items.extend(_plan_settings(repo, desired.repo_settings))
    items.extend(_plan_protection(repo, desired))
    return [replace(item, hold=hold) for item in items] if hold else items


def _plan_protection(repo: RepoState, desired: Desired) -> list[PlanItem]:
    """A proteção da branch default, ou o registro de que ela não foi observada.

    As duas leituras que a produzem falham juntas, e sem nenhuma delas não há como
    escolher entre criar, atualizar e não fazer nada. O item que sai daqui então
    não escolhe: ele diz o que faltou ler, e o `hold` diz o que a plataforma
    respondeu quando alguém tentou.
    """
    refused = repo.unobservable()
    if refused:
        return [
            PlanItem(
                action=OBSERVE_PROTECTION,
                target=repo.name,
                reason=(
                    f"a proteção de {repo.default_branch} não foi observada em "
                    f"{len(refused)} dimensão(ões) ({', '.join(name for name, _ in refused)}), e "
                    "nada é planejado sobre ela: um plano sobre proteção que ninguém "
                    "leu afirmaria o que ninguém mediu"
                ),
                hold="; ".join(sorted({why.reason for _, why in refused})),
            )
        ]

    items: list[PlanItem] = []
    if desired.ruleset is not None:
        items.extend(_plan_ruleset(repo, desired.ruleset))
    classic = repo.observed_classic_protection()
    if desired.retire_classic_protection and classic is not None:
        items.append(
            PlanItem(
                action=DELETE_CLASSIC_PROTECTION,
                target=repo.name,
                reason=(
                    f"proteção clássica ativa em {repo.default_branch} "
                    f"({classic.describe()}); o ruleset passa a ser a única "
                    "fonte de verdade sobre a branch"
                ),
                payload={"branch": repo.default_branch},
            )
        )
    return items


def _hold(repo: RepoState, desired: Desired, retrofitted: Collection[str]) -> str:
    """Por que este repo não pode receber o contrato de checks hoje, se não puder.

    O critério é o nome de check que o repo já exige: é o melhor proxy do que a
    CI dele publica. Se ele já exige exatamente o contrato, aplicar não muda o que
    um PR espera. Se exige outra coisa, ou nada, o contrato fixo penduraria todo
    PR do repo esperando um status que nunca sai com esse nome.

    A recusa da plataforma vem **antes** de tudo isso, inclusive de `--only`.
    Nomear um repo em `--only` é o operador afirmando que a CI dele já publica os
    nomes fixos de check; não é, e não teria como ser, uma afirmação sobre o que a
    leitura recusada teria dito. Deixar `--only` levantar esta retenção aplicaria
    convergência de branch a um repo cuja branch ninguém enxergou.
    """
    refused = repo.unobservable()
    if refused:
        return "; ".join(sorted({why.reason for _, why in refused}))

    contract = desired.check_contract
    if not contract or repo.name in retrofitted:
        return ""

    observed_checks = repo.required_check_contexts()
    if observed_checks == contract:
        return ""

    return (
        f"os checks exigidos hoje em {repo.default_branch} são "
        f"{', '.join(observed_checks) if observed_checks else 'nenhum'}, e o contrato fixo é "
        f"{', '.join(contract)}: aplicar agora penduraria todo PR deste repo esperando um "
        "check que a CI dele não publica com esse nome. Adiado até o retrofit de CI do repo; "
        f"depois dele, `--only {repo.name}` aplica"
    )


def _plan_settings(repo: RepoState, desired_settings: Mapping[str, Any]) -> list[PlanItem]:
    """O que falta na configuração do próprio repositório, que nenhum ruleset alcança."""
    divergences = _compare("", desired_settings, dict(repo.settings))
    if not divergences:
        return []

    return [
        PlanItem(
            action=UPDATE_REPO_SETTINGS,
            target=repo.name,
            reason=(
                f"configuração do repositório diverge do desejado em {len(divergences)} "
                "ponto(s): " + "; ".join(divergences)
            ),
            payload={"settings": dict(desired_settings)},
        )
    ]


def _plan_ruleset(repo: RepoState, desired_body: Mapping[str, Any]) -> list[PlanItem]:
    """O que falta para um único ruleset desejado governar a branch default.

    O ruleset a convergir é achado **pela branch que ele governa**, não pelo nome:
    procurar por nome faria um repo cujo ruleset se chama outra coisa ganhar um
    segundo ruleset sobre a mesma branch, que é exatamente a incoerência a evitar.
    """
    governing = repo.rulesets_governing_default_branch()
    every = repo.observed_rulesets()

    if not governing:
        return [
            PlanItem(
                action=CREATE_RULESET,
                target=repo.name,
                reason=(
                    f"nenhum ruleset governa a branch {repo.default_branch}"
                    + (f" (existem {len(every)} ruleset(s) fora dessa branch)" if every else "")
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
    """Uma lista comparável sem ordem: ordem de contexto ou de ator não é semântica."""
    return sorted(json.dumps(v, sort_keys=True, ensure_ascii=False) for v in values)


def _show(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)
