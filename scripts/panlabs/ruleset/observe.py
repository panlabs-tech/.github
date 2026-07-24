"""A observação: lê a org viva e a converte no estado que o planner recebe.

Duas metades deliberadamente separadas:

- `fetch_raw` toca a rede e não interpreta nada;
- `build_observed` é pura e não toca a rede.

É a segunda que as fixtures alimentam. Assim a fixture é um retrato fiel do que
a API devolve, e não uma invenção paralela que pode divergir da plataforma sem
que ninguém note.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from panlabs import gh
from panlabs.ruleset.model import ClassicProtection, Observed, RepoState, RulesetState

__all__ = ["build_observed", "fetch_raw", "observed_to_dict"]


def build_observed(raw: Mapping[str, Any]) -> Observed:
    """Converte o retrato cru da org no estado observado. Puro."""
    repos = tuple(_build_repo(entry) for entry in raw.get("repos", ()))
    return Observed(org=raw["org"], repos=repos)


def _build_repo(raw: Mapping[str, Any]) -> RepoState:
    return RepoState(
        name=raw["name"],
        default_branch=raw["default_branch"],
        rulesets=tuple(_build_ruleset(r) for r in raw.get("rulesets") or ()),
        classic_protection=_build_classic(raw.get("classic_protection")),
    )


def _build_ruleset(raw: Mapping[str, Any]) -> RulesetState:
    rules: dict[str, Mapping[str, Any]] = {}
    for rule in raw.get("rules") or ():
        rules[rule["type"]] = rule.get("parameters") or {}

    return RulesetState(
        id=raw["id"],
        name=raw["name"],
        target=raw.get("target", "branch"),
        enforcement=raw.get("enforcement", "active"),
        bypass_actors=tuple(raw.get("bypass_actors") or ()),
        conditions=raw.get("conditions") or {},
        rules=rules,
    )


def _build_classic(raw: Mapping[str, Any] | None) -> ClassicProtection | None:
    if raw is None:
        return None

    checks = raw.get("required_status_checks") or {}
    return ClassicProtection(
        required_status_checks=tuple(checks.get("contexts") or ()),
        strict=bool(checks.get("strict", False)),
        enforce_admins=bool((raw.get("enforce_admins") or {}).get("enabled", False)),
        required_signatures=bool((raw.get("required_signatures") or {}).get("enabled", False)),
        required_linear_history=bool(
            (raw.get("required_linear_history") or {}).get("enabled", False)
        ),
        requires_pull_request=raw.get("required_pull_request_reviews") is not None,
    )


def fetch_raw(org: str) -> dict[str, Any]:
    """O retrato cru da org viva, no formato que `build_observed` consome.

    Somente leitura, pelo `gh` já autenticado da máquina. Devolve o retrato cru em
    vez do estado já construído para que ele possa ser gravado como fixture: a
    fixture precisa ser o que a API disse, não o que nós entendemos dela.
    """
    repos: list[dict[str, Any]] = []
    for name in gh.repo_names(org):
        full_name = f"{org}/{name}"
        default_branch = gh.api(f"repos/{full_name}")["default_branch"]
        listing = gh.api(f"repos/{full_name}/rulesets") or []
        repos.append(
            {
                "name": full_name,
                "default_branch": default_branch,
                "rulesets": [gh.api(f"repos/{full_name}/rulesets/{r['id']}") for r in listing],
                "classic_protection": _fetch_classic(full_name, default_branch),
            }
        )
    return {"org": org, "repos": repos}


def _fetch_classic(full_name: str, branch: str) -> dict[str, Any] | None:
    try:
        return gh.api(f"repos/{full_name}/branches/{branch}/protection")
    except gh.GhNotFoundError:
        return None


def observed_to_dict(observed: Observed) -> dict[str, Any]:
    """Serializa o observado já normalizado, para inspeção rápida."""
    return {
        "org": observed.org,
        "repos": [
            {
                "name": repo.name,
                "default_branch": repo.default_branch,
                "rulesets": [
                    {
                        "id": rs.id,
                        "name": rs.name,
                        "target": rs.target,
                        "enforcement": rs.enforcement,
                        "governs_default_branch": rs.governs(repo.default_branch),
                        "rules": sorted(rs.rules),
                    }
                    for rs in repo.rulesets
                ],
                "classic_protection": (
                    repo.classic_protection.describe() if repo.classic_protection else None
                ),
            }
            for repo in observed.sorted_repos()
        ],
    }
