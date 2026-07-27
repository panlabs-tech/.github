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

Há um terceiro caso, e ele não é nenhum dos dois. Num repositório privado cujo
plano não oferece secret scanning, a API responde 200 com a chave presente e o
valor **nulo**: não omitiu, e também não disse nada. Isso não é token curto, e
por isso não é erro; e não é "desligado", e por isso não é `False`. Vira
`Unobservable`, que o planner converte em item retido com o motivo à vista.

Ausente e nulo têm causas diferentes, e só uma delas tem conserto pelo operador.
Tratá-las igual jogaria fora justamente a informação que diz o que fazer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from panlabs import gh
from panlabs.org.model import ActionsPolicy, Observed, OrgState, RepoState
from panlabs.plan import Unobservable

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


def _require(raw: Mapping[str, Any], key: str, source: str, *, admin: bool = False) -> Any:
    """O valor, ou um erro que diz de onde ele deveria ter vindo.

    Nenhuma dimensão tem valor de fallback, e é de propósito: um default aqui
    seria uma afirmação sobre a org que ninguém observou. Para as dimensões que
    só o administrador enxerga, o erro ainda diz como elevar o token, porque essa
    é de longe a causa mais provável de o campo faltar.
    """
    if key not in raw:
        hint = f": {ADMIN_SCOPE_HINT}" if admin else ""
        raise ValueError(f"resposta de `{source}` sem {key}{hint}")
    return raw[key]


def _build_org(raw: Mapping[str, Any]) -> OrgState:
    org = raw["org"]
    login = org["login"]
    source = f"orgs/{login}"
    actions = raw.get("actions_workflow_permissions") or {}
    actions_source = f"{source}/actions/permissions/workflow"

    return OrgState(
        login=login,
        actions=ActionsPolicy(
            can_approve_pull_requests=bool(
                _require(actions, "can_approve_pull_request_reviews", actions_source, admin=True)
            ),
            default_workflow_permissions=str(
                _require(actions, "default_workflow_permissions", actions_source, admin=True)
            ),
        ),
        description=org.get("description"),
        two_factor_required=bool(
            _require(org, "two_factor_requirement_enabled", source, admin=True)
        ),
        security_defaults={
            key: bool(value) for key, value in org.items() if key.endswith("_for_new_repositories")
        },
        pinned_repos=tuple(_require(raw, "pinned_repos", "graphql: pinnedItems")),
    )


def _build_repo(raw: Mapping[str, Any]) -> RepoState:
    name = raw["full_name"]
    source = f"repos/{name}"
    fixes_source = f"{source}/automated-security-fixes"
    private = bool(_require(raw, "private", source))
    security = _require(raw, "security_and_analysis", source, admin=True)
    fixes = _require(raw, "automated_security_fixes", fixes_source, admin=True)

    return RepoState(
        name=name,
        description=raw.get("description"),
        topics=tuple(raw.get("topics") or ()),
        wiki_enabled=bool(_require(raw, "has_wiki", source)),
        secret_scanning=_enabled(security, "secret_scanning", name, private=private),
        push_protection=_enabled(
            security, "secret_scanning_push_protection", name, private=private
        ),
        dependabot_alerts=bool(
            _require(raw, "vulnerability_alerts", f"{source}/vulnerability-alerts", admin=True)
        ),
        dependabot_security_updates=bool(_require(fixes, "enabled", fixes_source)),
        private=private,
    )


def _enabled(
    security: Mapping[str, Any] | None, key: str, name: str, *, private: bool
) -> bool | Unobservable:
    """O estado da dimensão, ou o registro de que a plataforma não o mostrou.

    O bloco inteiro vem nulo ou vem completo: não existe o caso de uma dimensão
    dentro dele responder e a outra não. Por isso a decisão é sobre o bloco, e as
    duas dimensões que moram nele saem juntas.
    """
    if security is None:
        return Unobservable(_no_security_block(name, private=private))
    return (security.get(key) or {}).get("status") == "enabled"


def _no_security_block(name: str, *, private: bool) -> str:
    """O motivo, escrito por nós porque aqui a plataforma não escreveu nenhum.

    Diferente do 403 de ruleset, que vem com a frase do GitHub dentro, este caso é
    um 200 silencioso: só o valor nulo chegou. O motivo então diz o que aconteceu
    (o campo veio nulo), o que se sabe do alvo (a visibilidade, observada e não
    suposta) e o que o desfaz. A visibilidade entra como fato lido, e não como
    explicação cravada, porque um repositório público com bloco nulo seria outra
    causa, e o texto não pode afirmar a que ninguém verificou.
    """
    saida = (
        "o repositório é privado, e a retenção sai sozinha quando ele virar público "
        "ou quando o plano da conta passar a oferecer a feature"
        if private
        else "a causa conhecida desta resposta é repositório privado sem a feature no "
        "plano, e este repositório é público: vale olhar antes de concluir qualquer coisa"
    )
    return (
        f"o GitHub devolveu `security_and_analysis` nulo em {name}, sem estado nenhum "
        f"para secret scanning nem para push protection; {saida}"
    )


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
        "private": repo.get("private"),
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


def _show(dimension: bool | Unobservable) -> Any:
    """A dimensão como JSON, sem deixar a não observada virar um booleano.

    Um `false` aqui diria que a dimensão está desligada, e é o operador que lê
    este dump com `--show-observed` antes de aprovar o plano. Um objeto no lugar
    de um booleano se vê de longe, e ainda serializa, que é mais do que a
    dataclass crua fazia.
    """
    return {"unobservable": dimension.reason} if isinstance(dimension, Unobservable) else dimension


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
                "private": repo.private,
                "secret_scanning": _show(repo.secret_scanning),
                "push_protection": _show(repo.push_protection),
                "dependabot_alerts": repo.dependabot_alerts,
                "dependabot_security_updates": repo.dependabot_security_updates,
            }
            for repo in observed.sorted_repos()
        ],
    }
