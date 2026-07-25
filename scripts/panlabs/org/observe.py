"""A observação: lê a org viva e a converte no estado que o planner recebe.

Duas metades deliberadamente separadas:

- `fetch_raw` toca a rede e não interpreta nada;
- `build_observed` é puro e não toca a rede.

É a segunda que as fixtures alimentam, e por isso o retrato cru guarda as
respostas da API com os nomes de campo que a API usa, mesmo quando só uma parte
delas é lida aqui.

Metade das dimensões desta configuração só é **legível** por quem administra a
org: sem escopo elevado o GitHub simplesmente omite os campos, em vez de negar a
resposta. Um campo omitido vira erro alto e explícito, nunca `False` por
omissão: "não consegui ler" não pode se disfarçar de "está desligado".
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from panlabs import gh
from panlabs.org.model import ActionsPolicy, Observed, OrgState, RepoState

__all__ = ["ADMIN_SCOPE_HINT", "build_observed", "fetch_raw", "observed_to_dict"]

ADMIN_SCOPE_HINT = (
    "essa dimensão só é legível por quem administra a org; "
    "eleve o token com `gh auth refresh -h github.com -s admin:org`"
)

PINNED_QUERY = """
query($login: String!) {
  organization(login: $login) {
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes { ... on Repository { nameWithOwner } }
    }
  }
}
"""


def build_observed(raw: Mapping[str, Any]) -> Observed:
    """Converte o retrato cru da org no estado observado. Puro."""
    return Observed(
        org=_build_org(raw),
        repos=tuple(_build_repo(entry) for entry in raw.get("repos", ())),
    )


def _build_org(raw: Mapping[str, Any]) -> OrgState:
    org = raw["org"]
    if "two_factor_requirement_enabled" not in org:
        raise ValueError(f"resposta de `orgs/{org.get('login')}` sem 2FA: {ADMIN_SCOPE_HINT}")

    actions = raw.get("actions_workflow_permissions") or {}
    return OrgState(
        login=org["login"],
        description=org.get("description"),
        two_factor_required=bool(org["two_factor_requirement_enabled"]),
        security_defaults={
            key: bool(value) for key, value in org.items() if key.endswith("_for_new_repositories")
        },
        actions=ActionsPolicy(
            can_approve_pull_requests=bool(actions.get("can_approve_pull_request_reviews", False)),
            default_workflow_permissions=str(actions.get("default_workflow_permissions", "read")),
        ),
        pinned_repos=tuple(raw.get("pinned_repos") or ()),
    )


def _build_repo(raw: Mapping[str, Any]) -> RepoState:
    name = raw["full_name"]
    security = raw.get("security_and_analysis")
    if security is None:
        raise ValueError(
            f"resposta de `repos/{name}` sem security_and_analysis: {ADMIN_SCOPE_HINT}"
        )

    return RepoState(
        name=name,
        description=raw.get("description"),
        topics=tuple(raw.get("topics") or ()),
        wiki_enabled=bool(raw.get("has_wiki", False)),
        secret_scanning=_enabled(security, "secret_scanning"),
        push_protection=_enabled(security, "secret_scanning_push_protection"),
        dependabot_alerts=bool(raw["vulnerability_alerts"]),
        dependabot_security_updates=bool(
            (raw.get("automated_security_fixes") or {}).get("enabled")
        ),
    )


def _enabled(security: Mapping[str, Any], key: str) -> bool:
    return (security.get(key) or {}).get("status") == "enabled"


def fetch_raw(org: str) -> dict[str, Any]:
    """O retrato cru da org viva, no formato que `build_observed` consome.

    Somente leitura, pelo `gh` já autenticado da máquina, e uma chamada por
    dimensão que a API não devolve junto com o repositório: alerts e security
    updates do Dependabot têm endpoint próprio, e os repos fixados só existem
    no GraphQL.
    """
    return {
        "org": gh.api(f"orgs/{org}"),
        "actions_workflow_permissions": gh.api(f"orgs/{org}/actions/permissions/workflow"),
        "pinned_repos": _fetch_pinned(org),
        "repos": [_fetch_repo(f"{org}/{name}") for name in gh.repo_names(org)],
    }


def _fetch_pinned(org: str) -> list[str]:
    payload = gh.graphql(PINNED_QUERY, login=org)
    nodes = payload["data"]["organization"]["pinnedItems"]["nodes"]
    return [node["nameWithOwner"] for node in nodes if node]


def _fetch_repo(full_name: str) -> dict[str, Any]:
    repo = gh.api(f"repos/{full_name}")
    return {
        "full_name": repo["full_name"],
        "description": repo.get("description"),
        "topics": repo.get("topics") or [],
        "has_wiki": repo.get("has_wiki"),
        "security_and_analysis": repo.get("security_and_analysis"),
        "vulnerability_alerts": _fetch_vulnerability_alerts(full_name),
        "automated_security_fixes": gh.api(f"repos/{full_name}/automated-security-fixes"),
    }


def _fetch_vulnerability_alerts(full_name: str) -> bool:
    """204 quando ligado, 404 quando desligado: o endpoint responde por presença.

    Aqui o 404 é resposta, não ausência: o repo veio da listagem da org viva
    segundos atrás. Falta de permissão é 403, e sobe como erro.
    """
    try:
        gh.api(f"repos/{full_name}/vulnerability-alerts")
    except gh.GhNotFoundError:
        return False
    return True


def observed_to_dict(observed: Observed) -> dict[str, Any]:
    """Serializa o observado já normalizado, para inspeção rápida."""
    org = observed.org
    return {
        "org": {
            "login": org.login,
            "description": org.description,
            "two_factor_required": org.two_factor_required,
            "security_defaults": dict(sorted(org.security_defaults.items())),
            "actions_can_approve_pull_requests": org.actions.can_approve_pull_requests,
            "pinned_repos": list(org.pinned_repos),
        },
        "repos": [
            {
                "name": repo.name,
                "description": repo.description,
                "topics": list(repo.topics),
                "wiki_enabled": repo.wiki_enabled,
                "secret_scanning": repo.secret_scanning,
                "push_protection": repo.push_protection,
                "dependabot_alerts": repo.dependabot_alerts,
                "dependabot_security_updates": repo.dependabot_security_updates,
            }
            for repo in observed.sorted_repos()
        ],
    }
