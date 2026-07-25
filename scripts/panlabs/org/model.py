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
    """A política de workflow da org, onde mora o botão que quebrou a esteira."""

    can_approve_pull_requests: bool
    default_workflow_permissions: str

    def as_body(self, *, can_approve: bool) -> dict[str, object]:
        """O corpo do PUT que muda só o que se quer mudar.

        Os dois campos viajam juntos porque a API os trata como um par: enviar um
        só devolveria o outro ao default, e a permissão default não é dimensão
        desta issue -- é estado a preservar.
        """
        return {
            "default_workflow_permissions": self.default_workflow_permissions,
            "can_approve_pull_request_reviews": can_approve,
        }


@dataclass(frozen=True)
class OrgState:
    """A org como ela está agora."""

    login: str
    description: str | None = None
    two_factor_required: bool = False
    security_defaults: Mapping[str, bool] = field(default_factory=dict)
    actions: ActionsPolicy = ActionsPolicy(
        can_approve_pull_requests=False, default_workflow_permissions="read"
    )
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
