"""A observação do checker: lê a org viva e a converte no estado que o planner recebe.

Duas metades deliberadamente separadas, como no ruleset:

- `fetch_raw` toca a rede (via `gh`: metadados, community profile, listagem de
  conteúdo da raiz) e não interpreta nada;
- `build_observed` é pura e não toca a rede -- é a fixture que a alimenta.

Falha de observação de UM repositório não derruba a corrida inteira: ela vira
o campo `error` daquele repositório, e o planner a converte num veredito de
erro isolado, sem contaminar os demais nem se disfarçar de deriva.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from panlabs import gh
from panlabs.checker.config import load_repo_types
from panlabs.checker.model import Observed, RepoObserved

__all__ = ["build_observed", "fetch_raw"]

PYTHON_MARKERS = ("pyproject.toml",)
NODE_MARKERS = ("package.json",)


def build_observed(raw: Mapping[str, Any]) -> Observed:
    """Converte o retrato cru da org no estado observado. Puro."""
    repos = tuple(_build_repo(entry) for entry in raw.get("repos", ()))
    return Observed(org=raw["org"], repos=repos)


def _build_repo(raw: Mapping[str, Any]) -> RepoObserved:
    if raw.get("error"):
        return RepoObserved(name=raw["name"], error=raw["error"])

    files = frozenset(raw.get("files") or ())
    return RepoObserved(
        name=raw["name"],
        tipo=raw.get("tipo"),
        surfaces=_surfaces_from(files),
        files=files,
        has_readme=bool(raw.get("has_readme", False)),
        has_license=bool(raw.get("has_license", False)),
    )


def _surfaces_from(files: frozenset[str]) -> frozenset[str]:
    surfaces: set[str] = set()
    if any(marker in files for marker in PYTHON_MARKERS):
        surfaces.add("python")
    if any(marker in files for marker in NODE_MARKERS):
        surfaces.add("node")
    if any(name.endswith(".tf") for name in files):
        surfaces.add("terraform")
    return frozenset(surfaces)


def fetch_raw(org: str) -> dict[str, Any]:
    """O retrato cru da org viva, no formato que `build_observed` consome.

    Somente leitura: metadados e community profile por `gh api`, presença de
    arquivo pela listagem de conteúdo da raiz. Uma falha isolada por
    repositório vira `error` naquele repositório em vez de derrubar a corrida
    inteira -- um 404 num repo não pode apagar a matriz dos outros.
    """
    types = load_repo_types()
    repos: list[dict[str, Any]] = []
    for name in gh.repo_names(org):
        full_name = f"{org}/{name}"
        try:
            repos.append(_fetch_repo(full_name, types.get(full_name)))
        except gh.GhError as exc:
            repos.append({"name": full_name, "error": str(exc)})
    return {"org": org, "repos": repos}


def _fetch_repo(full_name: str, tipo: str | None) -> dict[str, Any]:
    profile = gh.api(f"repos/{full_name}/community/profile") or {}
    profile_files = profile.get("files") or {}
    listing = gh.api(f"repos/{full_name}/contents/") or []
    return {
        "name": full_name,
        "tipo": tipo,
        "files": [entry["name"] for entry in listing],
        "has_readme": profile_files.get("readme") is not None,
        "has_license": profile_files.get("license") is not None,
    }
