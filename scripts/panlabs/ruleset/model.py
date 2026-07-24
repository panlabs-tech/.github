"""O estado observado da frota, no recorte que o ruleset enxerga.

O seam declara `observed = { repos[], gh_state, dirs[], disk }` como a uniao de
tudo que os scripts deste repo observam. O ruleset usa a fatia `repos` com o
estado de configuracao do GitHub dobrado dentro dela; o checker de conformidade
usara `dirs`/`disk` da mesma forma, sem que nenhum dos dois precise do outro.

Nada aqui decide: sao fatos lidos da plataforma, mais os predicados minimos que
o planner precisa para conversar sobre eles.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

__all__ = ["ClassicProtection", "Observed", "RepoState", "RulesetState"]

DEFAULT_BRANCH_REF = "~DEFAULT_BRANCH"
ALL_REFS = "~ALL"


@dataclass(frozen=True)
class RulesetState:
    """Um ruleset de repositorio, como a API o devolve."""

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
        """Diz se este ruleset alcanca a branch default do repo."""
        if self.target != "branch":
            return False
        refs = self.included_refs
        return (
            ALL_REFS in refs or DEFAULT_BRANCH_REF in refs or f"refs/heads/{default_branch}" in refs
        )

    def comparable(self) -> Mapping[str, Any]:
        """A parte do ruleset que se compara campo a campo com o desejado.

        As regras ficam de fora porque sao uma lista com chave propria (`type`)
        e exigem comparacao por conjunto, nao por posicao.
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
    """A protecao de branch classica, que o ruleset veio substituir."""

    required_status_checks: tuple[str, ...]
    strict: bool
    enforce_admins: bool
    required_signatures: bool
    required_linear_history: bool
    requires_pull_request: bool

    def describe(self) -> str:
        """Descreve, em uma frase, o que esta protecao segura hoje."""
        parts: list[str] = []
        if self.required_status_checks:
            parts.append(f"checks {', '.join(self.required_status_checks)}")
        else:
            parts.append("nenhum check exigido")
        if self.requires_pull_request:
            parts.append("PR exigido")
        if self.required_linear_history:
            parts.append("historico linear")
        if self.required_signatures:
            parts.append("commits assinados")
        if not self.enforce_admins:
            parts.append("nao se aplica a administradores")
        return "; ".join(parts)


@dataclass(frozen=True)
class RepoState:
    """Um repositorio da org viva e o estado de protecao da sua branch default."""

    name: str
    default_branch: str
    rulesets: tuple[RulesetState, ...] = ()
    classic_protection: ClassicProtection | None = None

    def rulesets_governing_default_branch(self) -> tuple[RulesetState, ...]:
        governing = [rs for rs in self.rulesets if rs.governs(self.default_branch)]
        return tuple(sorted(governing, key=lambda rs: rs.id))


@dataclass(frozen=True)
class Observed:
    """A frota como ela esta agora. A lista vem da org viva, nunca de constante."""

    org: str
    repos: tuple[RepoState, ...] = ()

    def sorted_repos(self) -> Sequence[RepoState]:
        return sorted(self.repos, key=lambda r: r.name)
