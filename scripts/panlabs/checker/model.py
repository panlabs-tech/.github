"""O estado observado da frota, no recorte que o checker de conformidade enxerga.

O seam declara `observed = { repo, tipo, superfícies[], arquivos[], metadados_gh }`
por repositório. Nada aqui decide: são fatos lidos da plataforma.

`error` é o canal de alarme do próprio checker: quando a observação de um
repositório falha (rede, credencial, 404), nenhum item do catálogo é avaliado
contra ele -- a falha vira um veredito de erro em vez de se disfarçar de
deriva de anatomia.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

__all__ = ["Observed", "RepoObserved"]


@dataclass(frozen=True)
class RepoObserved:
    """Um repositório da frota, no recorte que a anatomia avalia."""

    name: str
    tipo: str | None = None
    surfaces: frozenset[str] = field(default_factory=frozenset)
    files: frozenset[str] = field(default_factory=frozenset)
    has_readme: bool = False
    has_license: bool = False
    error: str | None = None


@dataclass(frozen=True)
class Observed:
    """A frota como ela está agora. A lista vem da org viva, nunca de constante."""

    org: str
    repos: tuple[RepoObserved, ...] = ()

    def sorted_repos(self) -> Sequence[RepoObserved]:
        return sorted(self.repos, key=lambda r: r.name)
