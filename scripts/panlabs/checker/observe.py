"""A observação do checker: lê a org viva e a converte no estado que o planner recebe.

Duas metades deliberadamente separadas, como no ruleset:

- `fetch_raw` toca a rede (via `gh`) e não interpreta nada;
- `build_observed` é pura e não toca a rede -- é a fixture que a alimenta.

**Quatro chamadas fixas por repositório, e nenhuma por arquivo.** Metadados e
community profile pela API REST, a árvore **recursiva** numa chamada só, e o
conteúdo do conjunto declarado numa consulta GraphQL com um apelido por arquivo.
O custo não cresce com o tamanho do repositório nem com o número de arquivos
lidos, que é o que torna a leitura de conteúdo viável na frota inteira.

**Ler mais não é escrever nada.** Nada aqui muta coisa alguma, em nenhum repo, em
nenhum momento: são quatro leituras e um `gh repo list`.

Falha de observação de UM repositório não derruba a corrida inteira: ela vira
o campo `error` daquele repositório, e o planner a converte num veredito de
erro isolado, sem contaminar os demais nem se disfarçar de deriva.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from panlabs import gh
from panlabs.checker.config import load_read_files, load_repo_types
from panlabs.checker.model import Observed, RepoObserved

__all__ = ["build_observed", "content_query", "contents_from", "fetch_raw"]

PYTHON_MARKERS = ("pyproject.toml",)
NODE_MARKERS = ("package.json",)

TRUNCATED = (
    "a árvore do repositório veio truncada pela API, e parte dela não foi observada; "
    "nenhum item é avaliado contra observação parcial, porque item que ninguém mediu "
    "não pode sair com cara de item que passou"
)


def build_observed(raw: Mapping[str, Any]) -> Observed:
    """Converte o retrato cru da org no estado observado. Puro."""
    repos = tuple(_build_repo(entry) for entry in raw.get("repos", ()))
    return Observed(org=raw["org"], repos=repos)


def _build_repo(raw: Mapping[str, Any]) -> RepoObserved:
    if raw.get("error"):
        return RepoObserved(name=raw["name"], error=raw["error"])
    if raw.get("truncated"):
        return RepoObserved(name=raw["name"], error=TRUNCATED)

    files = frozenset(raw.get("files") or ())
    return RepoObserved(
        name=raw["name"],
        tipo=raw.get("tipo"),
        surfaces=_surfaces_from(files),
        files=files,
        contents=dict(raw.get("contents") or {}),
        has_readme=bool(raw.get("has_readme", False)),
        has_license=bool(raw.get("has_license", False)),
        description=raw.get("description"),
        topics=frozenset(raw.get("topics") or ()),
        has_wiki=bool(raw.get("has_wiki", False)),
        license=raw.get("license"),
        private=bool(raw.get("private", False)),
    )


def _surfaces_from(files: frozenset[str]) -> frozenset[str]:
    """A superfície vem da árvore inteira, e não da raiz.

    Um manifesto em subpasta de monorepo é superfície igual à de um manifesto na
    raiz: o `tfbox` tem `web/package.json`, e enquanto só a raiz era listada o
    item de lockfile dele nem chegava a ser avaliado.
    """
    basenames = {path.rsplit("/", 1)[-1] for path in files}
    surfaces: set[str] = set()
    if any(marker in basenames for marker in PYTHON_MARKERS):
        surfaces.add("python")
    if any(marker in basenames for marker in NODE_MARKERS):
        surfaces.add("node")
    if any(name.endswith(".tf") for name in basenames):
        surfaces.add("terraform")
    return frozenset(surfaces)


# --- a consulta de conteúdo: pura de um lado e do outro da chamada -------------


def content_query(paths: Sequence[str]) -> str:
    """A consulta que pede, de uma vez, o conteúdo de todos os arquivos declarados.

    Um apelido por arquivo, posicional. É pura e testada porque é aqui que um
    defeito silencioso caberia: um apelido trocado devolveria o conteúdo do
    arquivo errado, e nenhum erro apareceria em lugar nenhum -- só um veredito de
    anatomia sobre o arquivo que ninguém leu.

    `HEAD` é a mesma referência que a árvore usa: nesta API ele resolve para a
    ponta da branch default, que é o que `_tree` pede pelo nome. Escrever a árvore
    numa referência e o conteúdo em outra faria os dois descreverem commits
    diferentes, e nada acusaria.
    """
    if not paths:
        return ""
    fields = " ".join(
        f"{_alias(index)}: object(expression: {json.dumps(f'HEAD:{path}')})"
        " { ... on Blob { text } }"
        for index, path in enumerate(paths)
    )
    return (
        "query($owner: String!, $name: String!) "
        "{ repository(owner: $owner, name: $name) { " + fields + " } }"
    )


def contents_from(answer: Any, paths: Sequence[str]) -> dict[str, str]:
    """Desfaz os apelidos, de volta para os caminhos que os pediram.

    Um caminho que voltou sem texto não entra: diretório e binário respondem
    assim, e nenhum dos dois é arquivo vazio.
    """
    repository = ((answer or {}).get("data") or {}).get("repository") or {}
    found: dict[str, str] = {}
    for index, path in enumerate(paths):
        blob = repository.get(_alias(index))
        text = blob.get("text") if isinstance(blob, Mapping) else None
        if text is not None:
            found[path] = str(text)
    return found


def _alias(index: int) -> str:
    return f"f{index}"


# --- a metade que toca a rede -------------------------------------------------


def fetch_raw(org: str) -> dict[str, Any]:
    """O retrato cru da org viva, no formato que `build_observed` consome.

    Somente leitura. Uma falha isolada por repositório vira `error` naquele
    repositório em vez de derrubar a corrida inteira -- um 404 num repo não pode
    apagar a matriz dos outros.
    """
    types = load_repo_types()
    read_files = load_read_files()
    repos: list[dict[str, Any]] = []
    for name in gh.repo_names(org):
        full_name = f"{org}/{name}"
        try:
            repos.append(_fetch_repo(org, name, types.get(full_name), read_files))
        except gh.GhError as exc:
            repos.append({"name": full_name, "error": str(exc)})
    return {"org": org, "repos": repos}


def _fetch_repo(org: str, name: str, tipo: str | None, read_files: Sequence[str]) -> dict[str, Any]:
    full_name = f"{org}/{name}"
    meta = gh.api(f"repos/{full_name}") or {}
    profile = gh.api(f"repos/{full_name}/community/profile") or {}
    profile_files = profile.get("files") or {}
    files, truncated = _tree(full_name, str(meta.get("default_branch") or "HEAD"))

    return {
        "name": full_name,
        "tipo": tipo,
        "files": files,
        "truncated": truncated,
        "contents": _contents(org, name, read_files),
        "has_readme": profile_files.get("readme") is not None,
        "has_license": profile_files.get("license") is not None,
        "description": meta.get("description"),
        "topics": sorted(meta.get("topics") or ()),
        "has_wiki": bool(meta.get("has_wiki")),
        "license": (meta.get("license") or {}).get("spdx_id"),
        "private": bool(meta.get("private")),
    }


def _tree(full_name: str, branch: str) -> tuple[list[str], bool]:
    """A árvore inteira numa chamada, e o aviso de que ela não veio inteira.

    `truncated` é a única resposta em que a API diz que mentiu por omissão, e
    ignorá-la produziria exatamente o falso-negativo que a árvore recursiva veio
    consertar: arquivo que existe, não foi visto, e o item passa.
    """
    answer = gh.api(f"repos/{full_name}/git/trees/{branch}?recursive=1") or {}
    paths = sorted(
        str(entry["path"]) for entry in answer.get("tree") or () if entry.get("type") == "blob"
    )
    return paths, bool(answer.get("truncated"))


def _contents(org: str, name: str, read_files: Sequence[str]) -> dict[str, str]:
    if not read_files:
        return {}
    return contents_from(gh.graphql(content_query(read_files), owner=org, name=name), read_files)
