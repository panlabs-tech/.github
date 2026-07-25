"""A análise estática advisory: a que reporta achado e nunca trava merge.

A spec de Org #2 pede análise de código estática e, no mesmo fôlego, decide
deixar de fora a regra de ruleset que a exigiria. Não é meia decisão: aquela
regra bloqueia por "análise em andamento" e por "ferramenta não configurada",
**sem timeout**. Os dois motivos penduram o merge sem nenhum alerta por trás,
que é o oposto do que uma análise serve para fazer.

Uma decisão de não exigir some do dado: `config/ruleset.json` não tem como
carregar a ausência de uma regra. Este módulo é o que dá voz a ela, para que o
teste possa afirmar a decisão em vez de o silêncio passar por esquecimento.

Consequência de desenho, e não detalhe: como nenhum destes nomes é required, o
workflow de análise pode publicar **um status por linguagem**, com o nome da
perna de matrix anexado. É exatamente a forma que `rollup.py` existe para evitar
em required check, e que aqui é inofensiva.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from panlabs.ruleset.model import CHECKS_RULE_TYPE, check_contexts_of

__all__ = [
    "ANALYZE_JOB",
    "CODE_SCANNING_JOB",
    "CODE_SCANNING_RULE_TYPE",
    "CODE_SCANNING_WORKFLOW",
    "RESULT_CHECK_NAMES",
    "code_scanning_check_names",
    "demands_code_scanning",
    "is_code_scanning_check",
]

CODE_SCANNING_RULE_TYPE = "code_scanning"
"""O `type` da regra de ruleset que exigiria a análise, como a API a nomeia."""

CODE_SCANNING_WORKFLOW = "code-scanning.yml"
"""O reusable workflow da análise, em `.github/workflows/`."""

CODE_SCANNING_JOB = "code-scanning"
"""O id do job que o chama, no caller de cada consumidor."""

ANALYZE_JOB = "analyze"
"""O id do job dentro do reusable workflow, que entra no nome publicado."""

RESULT_CHECK_NAMES = frozenset({"CodeQL", "Code scanning results / CodeQL"})
"""Os checks que o próprio code scanning publica, além dos jobs do workflow.

Não saem de job nenhum: quem os cria é a plataforma, ao receber os achados. São
os que mais pareceriam exigíveis, porque têm nome curto e estável, e são
justamente os que pendurariam o merge esperando análise.
"""


def code_scanning_check_names(languages: Sequence[str]) -> frozenset[str]:
    """Os nomes de status que a análise publica, um por linguagem.

    Um job que chama reusable workflow via `uses:` publica
    `<job do caller> / <job do chamado>`, e a perna de matrix entra entre
    parênteses. Aqui isso é seguro: nenhum destes nomes é exigido.
    """
    return frozenset(f"{CODE_SCANNING_JOB} / {ANALYZE_JOB} ({language})" for language in languages)


def is_code_scanning_check(context: str) -> bool:
    """Diz se este nome de status check vem da análise estática.

    Por prefixo de job, e não por lista fechada: a lista de linguagens varia de
    repo para repo, e um contrato que só reconhecesse as linguagens de hoje
    deixaria passar o repo que amanhã acrescentar uma.
    """
    return context in RESULT_CHECK_NAMES or context.split(" / ")[0] == CODE_SCANNING_JOB


def demands_code_scanning(ruleset: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Os motivos pelos quais este ruleset exigiria a análise. Vazio é advisory.

    Duas formas de exigir, e as duas contam: a regra dedicada e um required
    status check com o nome que a análise publica. A segunda é a que entraria
    sem ninguém perceber, porque parece só mais um nome na lista de checks.

    Um ruleset ainda não decidido (`None`) não exige nada, como não exige nada
    mais: é ausência de decisão, não decisão de não exigir.
    """
    if ruleset is None:
        return ()

    reasons: list[str] = []
    for rule in ruleset.get("rules") or ():
        if rule.get("type") == CODE_SCANNING_RULE_TYPE:
            reasons.append(
                f"o ruleset carrega a regra {CODE_SCANNING_RULE_TYPE}, que pendura o merge "
                "por análise em andamento e por ferramenta não configurada, sem timeout"
            )
        if rule.get("type") == CHECKS_RULE_TYPE:
            reasons.extend(
                f"o ruleset exige o status check {context!r}, que vem da análise estática"
                for context in check_contexts_of(rule.get("parameters") or {})
                if is_code_scanning_check(context)
            )
    return tuple(reasons)
