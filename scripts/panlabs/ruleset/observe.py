"""A observação: lê a org viva e a converte no estado que o planner recebe.

Duas metades deliberadamente separadas:

- `fetch_raw` toca a rede e não interpreta nada;
- `build_observed` é pura e não toca a rede.

É a segunda que as fixtures alimentam. Assim a fixture é um retrato fiel do que
a API devolve, e não uma invenção paralela que pode divergir da plataforma sem
que ninguém note.

Uma recusa também é resposta, e o retrato a guarda como tal. Num repositório
privado cujo plano não oferece rulesets, as duas leituras de proteção respondem
403, e a frase que o GitHub manda junto vai inteira para o retrato, sob a chave
`unobservable`. As chaves da dimensão recusada ficam **ausentes**, em vez de
aparecerem vazias: `rulesets: []` já quer dizer "nenhum ruleset governa esta
branch", e emprestar esse valor para "não consegui ler" faria a fixture afirmar
o que ninguém mediu.

Só a recusa **por plano** é tratada assim. Um 403 de permissão continua derrubando
a corrida, porque ele tem conserto pelo operador, e engoli-lo esconderia o conserto.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from panlabs import gh
from panlabs.plan import Unobservable
from panlabs.ruleset.model import (
    REPO_SETTINGS_KEYS,
    ClassicProtection,
    Observed,
    RepoState,
    RulesetState,
)

__all__ = ["build_observed", "fetch_raw", "observed_to_dict"]

RULESETS = "rulesets"
CLASSIC_PROTECTION = "classic_protection"
"""Os nomes das duas dimensões de proteção, iguais no retrato cru e no observado.

Uma constante para cada porque elas atravessam três fronteiras (o que a rede
gravou, o que o modelo expõe e o que o plano imprime), e três textos soltos para
a mesma dimensão divergiriam calados.
"""


def build_observed(raw: Mapping[str, Any]) -> Observed:
    """Converte o retrato cru da org no estado observado. Puro."""
    repos = tuple(_build_repo(entry) for entry in raw.get("repos", ()))
    return Observed(org=raw["org"], repos=repos)


def _build_repo(raw: Mapping[str, Any]) -> RepoState:
    refused: Mapping[str, str] = raw.get("unobservable") or {}
    return RepoState(
        name=raw["name"],
        default_branch=raw["default_branch"],
        rulesets=(
            Unobservable(refused[RULESETS])
            if RULESETS in refused
            else tuple(_build_ruleset(r) for r in raw.get(RULESETS) or ())
        ),
        classic_protection=(
            Unobservable(refused[CLASSIC_PROTECTION])
            if CLASSIC_PROTECTION in refused
            else _build_classic(raw.get(CLASSIC_PROTECTION))
        ),
        settings=dict(raw.get("settings") or {}),
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
        repo = gh.api(f"repos/{full_name}")
        default_branch = repo["default_branch"]
        entry: dict[str, Any] = {
            "name": full_name,
            "default_branch": default_branch,
            # A mesma resposta que deu a branch default já carrega as dimensões
            # de repositório: observá-las não custa nenhuma chamada a mais.
            "settings": {k: repo[k] for k in REPO_SETTINGS_KEYS if k in repo},
        }
        # As duas leituras de proteção são as únicas que a plataforma recusa por
        # plano, e cada uma é capturada sozinha: elas falham juntas hoje, e supor
        # que sempre vão falhar juntas seria uma conclusão sobre a plataforma que
        # ninguém verificou. Qualquer outra falha continua subindo, porque as
        # outras têm conserto pelo operador e engoli-las esconderia o conserto.
        refused: dict[str, str] = {}
        try:
            entry[RULESETS] = _fetch_rulesets(full_name)
        except gh.GhUpgradeRequiredError as exc:
            refused[RULESETS] = str(exc)
        try:
            entry[CLASSIC_PROTECTION] = _fetch_classic(full_name, default_branch)
        except gh.GhUpgradeRequiredError as exc:
            refused[CLASSIC_PROTECTION] = str(exc)
        if refused:
            entry["unobservable"] = refused
        repos.append(entry)
    return {"org": org, "repos": repos}


def _fetch_rulesets(full_name: str) -> list[Any]:
    listing = gh.api(f"repos/{full_name}/rulesets") or []
    return [gh.api(f"repos/{full_name}/rulesets/{r['id']}") for r in listing]


def _fetch_classic(full_name: str, branch: str) -> dict[str, Any] | None:
    """404 é resposta (não há proteção clássica); 403 de plano é recusa, e sobe.

    A distinção importa aqui mais do que em qualquer outro lugar: as duas viram
    "sem proteção clássica" se a gente deixar, e uma delas apagaria do plano o
    item que aposenta uma proteção que existe.
    """
    try:
        return gh.api(f"repos/{full_name}/branches/{branch}/protection")
    except gh.GhNotFoundError:
        return None


def observed_to_dict(observed: Observed) -> dict[str, Any]:
    """Serializa o observado já normalizado, para inspeção rápida."""
    return {
        "org": observed.org,
        "repos": [_repo_to_dict(repo) for repo in observed.sorted_repos()],
    }


def _repo_to_dict(repo: RepoState) -> dict[str, Any]:
    """O dump **omite** a dimensão que ninguém observou, em vez de zerá-la.

    `classic_protection: null` já quer dizer "não existe proteção clássica", e
    `rulesets: []` já quer dizer "nenhum ruleset". Emprestar qualquer um dos dois
    para "não consegui ler" faria a inspeção rápida, que existe justamente para o
    operador conferir antes de aprovar, afirmar o oposto do que houve.
    """
    entry: dict[str, Any] = {
        "name": repo.name,
        "default_branch": repo.default_branch,
        "settings": dict(repo.settings),
    }

    refused = repo.unobservable()
    if refused:
        entry["unobservable"] = {dimension: why.reason for dimension, why in refused}

    if not isinstance(repo.rulesets, Unobservable):
        entry[RULESETS] = [
            {
                "id": rs.id,
                "name": rs.name,
                "target": rs.target,
                "enforcement": rs.enforcement,
                "governs_default_branch": rs.governs(repo.default_branch),
                "rules": sorted(rs.rules),
            }
            for rs in repo.rulesets
        ]
    if not isinstance(repo.classic_protection, Unobservable):
        entry[CLASSIC_PROTECTION] = (
            repo.classic_protection.describe() if repo.classic_protection else None
        )
    if not refused:
        # Depende das duas dimensões: com uma delas cega, a conta não fecha.
        entry["required_check_contexts"] = list(repo.required_check_contexts())
    return entry
