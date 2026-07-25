"""O estado observado da frota, no recorte que o ruleset enxerga.

O seam declara `observed = { repos[], gh_state, dirs[], disk }` como a união de
tudo que os scripts deste repo observam. O ruleset usa a fatia `repos` com o
estado de configuração do GitHub dobrado dentro dela; o checker de conformidade
usará `dirs`/`disk` da mesma forma, sem que nenhum dos dois precise do outro.

Nada aqui decide: são fatos lidos da plataforma, mais os predicados mínimos que
o planner precisa para conversar sobre eles.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "REPO_SETTINGS_KEYS",
    "ClassicProtection",
    "Observed",
    "RepoState",
    "RulesetState",
    "check_contexts_of",
]

DEFAULT_BRANCH_REF = "~DEFAULT_BRANCH"
ALL_REFS = "~ALL"

CHECKS_RULE_TYPE = "required_status_checks"
"""O `type` da regra de status check, como a API a nomeia."""

CHECKS_RULE_CONTEXTS = "required_status_checks"
"""A chave, dentro dos parâmetros dessa regra, que lista os checks exigidos.

Tem o mesmo texto do `type` e não é a mesma coisa: uma nomeia a regra, a outra
nomeia um campo dentro dela. Duas constantes porque são dois conceitos, e ler
`rules[X][X]` com uma constante só passaria por erro de digitação.
"""


def check_contexts_of(parameters: Mapping[str, Any]) -> tuple[str, ...]:
    """Os nomes de check listados nos parâmetros de uma regra de status check.

    Um leitor só, usado tanto sobre o ruleset observado quanto sobre o desejado:
    são o mesmo formato de dado, e duas leituras divergiriam calada.
    """
    checks = parameters.get(CHECKS_RULE_CONTEXTS) or ()
    return tuple(sorted(check["context"] for check in checks if "context" in check))


REPO_SETTINGS_KEYS = (
    "allow_auto_merge",
    "allow_merge_commit",
    "allow_rebase_merge",
    "allow_squash_merge",
    "delete_branch_on_merge",
)
"""As dimensões de repositório que este script enxerga, em `GET /repos/{owner}/{repo}`.

São as mesmas chaves que a configuração desejada pode declarar: observar uma
coisa e desejar outra faria o plano nunca esvaziar. O ruleset não alcança nenhuma
delas, e é por isso que elas existem aqui: método de merge, deleção de branch no
merge e auto-merge são configuração do repositório, não regra de branch.
"""


@dataclass(frozen=True)
class RulesetState:
    """Um ruleset de repositório, como a API o devolve."""

    id: int
    name: str
    target: str
    enforcement: str
    bypass_actors: tuple[Any, ...]
    conditions: Mapping[str, Any]
    rules: Mapping[str, Mapping[str, Any]]

    @property
    def included_refs(self) -> tuple[str, ...]:
        ref_name = self.conditions.get("ref_name") or {}
        return tuple(ref_name.get("include") or ())

    def governs(self, default_branch: str) -> bool:
        """Diz se este ruleset alcança a branch default do repo."""
        if self.target != "branch":
            return False
        refs = self.included_refs
        return (
            ALL_REFS in refs or DEFAULT_BRANCH_REF in refs or f"refs/heads/{default_branch}" in refs
        )

    def required_check_contexts(self) -> tuple[str, ...]:
        """Os nomes de check que este ruleset exige hoje."""
        return check_contexts_of(self.rules.get(CHECKS_RULE_TYPE) or {})

    def comparable(self) -> Mapping[str, Any]:
        """A parte do ruleset que se compara campo a campo com o desejado.

        As regras ficam de fora porque são uma lista com chave própria (`type`)
        e exigem comparação por conjunto, não por posição.
        """
        return {
            "name": self.name,
            "target": self.target,
            "enforcement": self.enforcement,
            "bypass_actors": list(self.bypass_actors),
            "conditions": dict(self.conditions),
        }


@dataclass(frozen=True)
class ClassicProtection:
    """A proteção de branch clássica, que o ruleset veio substituir."""

    required_status_checks: tuple[str, ...]
    strict: bool
    enforce_admins: bool
    required_signatures: bool
    required_linear_history: bool
    requires_pull_request: bool

    def describe(self) -> str:
        """Descreve, em uma frase, tudo que esta proteção segura hoje.

        A descrição inteira vira o motivo do item que a aposenta, então ela não
        pode omitir nada: um plano que apaga uma garantia sem nomeá-la não é
        revisável.

        Cada dimensão é nomeada nas duas polaridades, e não só quando está ligada.
        Calar sobre uma garantia ausente pareceria omissão, e calar sobre uma
        presente apagaria justamente o que o operador precisava ver antes de
        aprovar: "se aplica a administradores" é a mais forte que ela pode ter.
        """
        checks = ", ".join(self.required_status_checks)
        return "; ".join(
            [
                f"checks {checks}{' (estrito)' if self.strict else ''}"
                if self.required_status_checks
                else "nenhum check exigido",
                "PR exigido" if self.requires_pull_request else "PR não exigido",
                "histórico linear" if self.required_linear_history else "sem histórico linear",
                "commits assinados" if self.required_signatures else "sem exigir assinatura",
                "se aplica a administradores"
                if self.enforce_admins
                else "não se aplica a administradores",
            ]
        )


@dataclass(frozen=True)
class RepoState:
    """Um repositório da org viva e o estado de proteção da sua branch default."""

    name: str
    default_branch: str
    rulesets: tuple[RulesetState, ...] = ()
    classic_protection: ClassicProtection | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)

    def rulesets_governing_default_branch(self) -> tuple[RulesetState, ...]:
        governing = [rs for rs in self.rulesets if rs.governs(self.default_branch)]
        return tuple(sorted(governing, key=lambda rs: rs.id))

    def required_check_contexts(self) -> tuple[str, ...]:
        """Os nomes de check exigidos hoje na branch default, venham de onde vierem.

        Ruleset e proteção clássica entram na mesma conta porque a pergunta é uma
        só: quais nomes de status a CI deste repo já precisa publicar para que um
        PR consiga mergear. É o melhor proxy disponível para o que ela publica,
        e é o critério que decide se o contrato fixo de checks pode alcançá-lo hoje.
        """
        names: set[str] = set()
        for ruleset in self.rulesets_governing_default_branch():
            names.update(ruleset.required_check_contexts())
        if self.classic_protection is not None:
            names.update(self.classic_protection.required_status_checks)
        return tuple(sorted(names))


@dataclass(frozen=True)
class Observed:
    """A frota como ela está agora. A lista vem da org viva, nunca de constante."""

    org: str
    repos: tuple[RepoState, ...] = ()

    def sorted_repos(self) -> Sequence[RepoState]:
        return sorted(self.repos, key=lambda r: r.name)
