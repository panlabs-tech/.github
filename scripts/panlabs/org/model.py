"""O estado observado, no recorte que a configuração de org e repo enxerga.

O seam declara `observed = { repos[], gh_state, dirs[], disk }` como a união de
tudo que os scripts deste repo observam. Aqui a fatia é `gh_state` (a org: sua
política de Actions, sua postura de segurança, sua vitrine) mais `repos` com a
configuração de cada um dobrada dentro.

Nada aqui decide: são fatos lidos da plataforma. As dimensões são deliberadamente
campos separados, e não um dicionário genérico, porque cada uma diverge sozinha e
o planner precisa poder falar de uma sem tocar nas outras.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

__all__ = ["ActionsPolicy", "Observed", "OrgState", "RepoState"]


@dataclass(frozen=True)
class ActionsPolicy:
    """A política de workflow da org, onde mora o botão que quebrou a esteira.

    A permissão default do token de workflow não é dimensão desta configuração,
    mas é lida junto porque a API trata as duas como um par: quem escreve uma
    precisa reenviar a outra, e reenviá-la exige tê-la observado.
    """

    can_approve_pull_requests: bool
    default_workflow_permissions: str


@dataclass(frozen=True)
class OrgState:
    """A org como ela está agora.

    A política de Actions não tem default: um default aqui seria "a esteira está
    desligada" dito por quem não observou nada, e é justamente essa dimensão que
    esta configuração existe para vigiar.
    """

    login: str
    actions: ActionsPolicy
    description: str | None = None
    two_factor_required: bool = False
    security_defaults: Mapping[str, bool] = field(default_factory=dict)
    pinned_repos: tuple[str, ...] = ()
    """Os repos fixados no perfil, em ordem. A ordem é semântica: ela é a vitrine."""


@dataclass(frozen=True)
class RepoState:
    """Um repositório da org viva, no recorte que esta configuração governa."""

    name: str
    description: str | None = None
    topics: tuple[str, ...] = ()
    wiki_enabled: bool = False
    secret_scanning: bool = False
    push_protection: bool = False
    dependabot_alerts: bool = False
    dependabot_security_updates: bool = False


@dataclass(frozen=True)
class Observed:
    """A org e a frota como estão agora. A lista vem da org viva, nunca de constante."""

    org: OrgState
    repos: tuple[RepoState, ...] = ()

    def sorted_repos(self) -> Sequence[RepoState]:
        return sorted(self.repos, key=lambda r: r.name)
