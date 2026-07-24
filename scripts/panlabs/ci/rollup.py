"""O contrato de nomes de status check: a correção ao defeito do #59.

O #59 padronizou ids de job fixos e, no mesmo fôlego, previu disparar
`checks-node` e/ou `checks-python` via `strategy.matrix`. As duas decisões não
coexistem: um job de matrix não publica o status com o nome do job, publica um
status por perna, com os valores da matriz anexados ao nome. Um required check
de nome fixo nunca casaria, e um repo sem superfície alguma (o `skills`)
pendurava o merge para sempre esperando um check que nunca roda.

A correção é o job de **rollup**: cada repo consumidor expõe um job de id
fixo (`checks`) que declara `needs` sobre as pernas por superfície que aquele
repo tem, e agrega o resultado delas explicitamente. `needs` varia livremente
repo a repo; o nome publicado, não. Isso é o que este módulo modela e
testa em `tests/test_ci_rollup.py`, sem rodar workflow nenhum.

O footgun que mata o desenho ingênuo: sem `if: always()` mais checagem
explícita de `needs.*.result`, uma perna vermelha faz o rollup ser **pulado**
em vez de **reprovado**, e pulado não satisfaz um required check do jeito que
reprovado faz, mas também não bloqueia. `rollup_conclusion` é essa checagem,
isolada do YAML para ser testável.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

__all__ = [
    "ROLLUP_CHECK_NAME",
    "SECURITY_CHECK_NAME",
    "RollupJob",
    "build_rollup",
    "required_status_names",
    "rollup_conclusion",
]

ROLLUP_CHECK_NAME = "checks"
SECURITY_CHECK_NAME = "security"

_SAFE_LEG_RESULTS = frozenset({"success", "skipped"})


@dataclass(frozen=True)
class RollupJob:
    """O job de rollup que um repo consumidor declara no seu caller workflow.

    `name` é o nome de status publicado: fixo, por construção. `needs` é a
    lista de pernas por superfície, que varia livremente repo a repo sem
    afetar `name`: é essa separação que sustenta a invariância.
    """

    name: str
    needs: tuple[str, ...]


def build_rollup(surfaces: Sequence[str]) -> RollupJob:
    """O job de rollup para um repo com estas superfícies de checks.

    Cada superfície vira uma perna `checks-<superfície>` em `needs`. O nome
    publicado continua `checks` mesmo com zero pernas: é isso que faz um
    repo sem superfície alguma ainda reportar o required check em vez de
    pendurar o merge esperando um check que nunca roda.
    """
    return RollupJob(
        name=ROLLUP_CHECK_NAME,
        needs=tuple(f"checks-{surface}" for surface in surfaces),
    )


def required_status_names(surfaces: Sequence[str]) -> frozenset[str]:
    """O conjunto de status checks obrigatórios que um consumidor publica.

    Constante por construção: decorre da forma do rollup, não do número de
    superfícies. Exercitado com zero, uma e duas superfícies, este é o teste
    que teria pego o defeito original do #59.
    """
    rollup = build_rollup(surfaces)
    return frozenset({rollup.name, SECURITY_CHECK_NAME})


def rollup_conclusion(leg_results: Mapping[str, str]) -> str:
    """A conclusão do rollup, dados os `needs.*.result` brutos das pernas.

    Espelha a checagem explícita que o passo "agregar o resultado das pernas
    por superfície" do job `checks` em `.github/workflows/pr-checks.yml`
    precisa ter ao lado de `if: always()`: as duas cópias da regra (esta e a
    do bash) precisam mudar juntas se o critério de "perna segura" mudar. Uma
    perna ausente (repo sem superfície) resulta em sucesso trivial; qualquer
    perna fora de `success`/`skipped` (reprovada, cancelada, ou qualquer outra
    conclusão) reprova o rollup inteiro.
    """
    if any(result not in _SAFE_LEG_RESULTS for result in leg_results.values()):
        return "failure"
    return "success"
