"""A observação do checker: o que ela enxerga, e o que ela recusa a fingir.

Duas metades, como no resto do repo: `fetch_raw` toca a rede e não interpreta
nada, `build_observed` interpreta e não toca a rede. Todo teste daqui vive na
segunda metade, mais as duas funções puras que montam e desmontam a consulta de
conteúdo -- que é onde um defeito silencioso caberia, porque um apelido trocado
devolveria o conteúdo do arquivo errado sem erro nenhum.

O falso-negativo que este arquivo existe para travar está registrado no baseline
de 2026-07-24: a superfície Node do `tfbox` não era detectada porque o manifesto
mora numa subpasta do monorepo, e o item de lockfile **nem chegava a ser
avaliado** ali. Não é falso positivo; é pior, é um item que ninguém mede e que
parece verde.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from panlabs import gh
from panlabs.checker.model import Observed
from panlabs.checker.observe import build_observed, content_query, contents_from

FIXTURES = Path(__file__).parent / "fixtures"
FLEET = FIXTURES / "checker-fleet-2026-07-25.json"


def repo(name: str, **fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": name,
        "tipo": None,
        "files": [],
        "contents": {},
        "has_readme": True,
        "has_license": True,
        "description": "um repo qualquer",
        "topics": [],
        "has_wiki": False,
        "license": "MIT",
    }
    base.update(fields)
    return base


def observed(*repos: dict[str, Any]) -> Observed:
    return build_observed({"org": "panlabs-tech", "repos": list(repos)})


def only(*repos: dict[str, Any]):
    return observed(*repos).repos[0]


# --- a árvore recursiva, no lugar da listagem da raiz --------------------------


def test_a_manifest_in_a_subfolder_is_a_surface_just_like_one_at_the_root():
    """O falso-negativo do `tfbox`: o manifesto Node mora numa subpasta do monorepo."""
    state = only(
        repo(
            "panlabs-tech/tfbox",
            files=["aws/iam-role/main.tf", "package-lock.json", "web/package.json"],
        )
    )

    assert state.surfaces == frozenset({"terraform", "node"})


def test_a_python_manifest_in_a_subfolder_is_a_surface_too():
    state = only(repo("panlabs-tech/app", files=["apps/api/pyproject.toml"]))

    assert state.surfaces == frozenset({"python"})


def test_a_repo_with_no_manifest_anywhere_has_no_surface_at_all():
    """Skills e dotfiles são o caso real de stack vazia, e são o fixture que importa."""
    state = only(repo("panlabs-tech/skills", files=["README.md", "LICENSE", "docs/uso.md"]))

    assert state.surfaces == frozenset()


def test_the_full_path_is_what_is_observed_and_the_basename_is_derived_from_it():
    state = only(repo("panlabs-tech/app", files=["apps/api/pyproject.toml"]))

    assert "apps/api/pyproject.toml" in state.files
    assert "pyproject.toml" in state.basenames
    assert "pyproject.toml" not in state.files


def test_a_truncated_tree_is_an_observation_error_and_never_a_green_repo():
    """Uma árvore truncada é observação parcial, e parcial não pode parecer conforme.

    É o mesmo defeito do falso-negativo da listagem raiz, com outra causa: item
    que ninguém mediu saindo com cara de item que passou.
    """
    state = only(repo("panlabs-tech/gigante", files=["README.md"], truncated=True))

    assert state.error is not None
    assert "truncada" in state.error


# --- o conteúdo de um conjunto declarado de arquivos --------------------------


def test_the_content_of_a_declared_file_lands_in_the_observed_state():
    state = only(repo("panlabs-tech/x", contents={"AGENTS.md": "# AGENTS\n@CLAUDE.md"}))

    assert state.content("AGENTS.md") == "# AGENTS\n@CLAUDE.md"


def test_a_declared_file_the_repo_does_not_have_reads_as_absent_and_not_as_empty():
    """Ausente e vazio são estados diferentes, e um item de slot distingue os dois."""
    state = only(repo("panlabs-tech/x", contents={"AGENTS.md": ""}))

    assert state.content("AGENTS.md") == ""
    assert state.content("CLAUDE.md") is None


def test_a_file_nobody_declared_has_no_content_even_when_it_exists_in_the_tree():
    """O conjunto é dado: a árvore diz que o arquivo existe, e ninguém pediu para lê-lo."""
    state = only(repo("panlabs-tech/x", files=["README.md"], contents={}))

    assert state.content("README.md") is None


# --- a consulta de conteúdo: um apelido por arquivo, uma chamada por repo ------


def test_the_content_query_asks_for_every_declared_path_in_a_single_query():
    query = content_query(("AGENTS.md", "docs/agents/domain.md"))

    assert query.count("object(expression:") == 2
    assert '"HEAD:AGENTS.md"' in query
    assert '"HEAD:docs/agents/domain.md"' in query


def test_the_answer_is_mapped_back_to_the_path_that_asked_for_it():
    """O apelido é posicional, e trocá-lo devolveria o conteúdo do arquivo errado."""
    paths = ("a.md", "b.md", "c.md")
    answer = {
        "data": {
            "repository": {
                "f0": {"text": "sou o a"},
                "f1": None,
                "f2": {"text": "sou o c"},
            }
        }
    }

    assert contents_from(answer, paths) == {"a.md": "sou o a", "c.md": "sou o c"}


def test_a_path_that_came_back_without_text_is_absent_instead_of_empty():
    """Diretório e binário respondem sem texto, e nenhum dos dois é arquivo vazio."""
    answer = {"data": {"repository": {"f0": {}}}}

    assert contents_from(answer, ("docs",)) == {}


def test_an_empty_declared_set_asks_nothing_at_all():
    assert content_query(()) == ""
    assert contents_from({}, ()) == {}


# --- os metadados de plataforma ------------------------------------------------


def test_description_topics_wiki_and_license_enter_the_observed_state():
    """A fronteira de verificação atravessa a de decisão de propósito (spec de Repo #4).

    Eles são observáveis por leitura e ficariam sem vigia nenhum se o checker não
    os lesse: nenhum deles mora no working tree.
    """
    state = only(
        repo(
            "panlabs-tech/tfbox",
            description="módulos Terraform para AWS",
            topics=["aws", "terraform"],
            has_wiki=True,
            license="Apache-2.0",
        )
    )

    assert state.description == "módulos Terraform para AWS"
    assert state.topics == frozenset({"aws", "terraform"})
    assert state.has_wiki is True
    assert state.license == "Apache-2.0"


def test_a_repo_with_no_description_reads_as_absent_and_not_as_an_empty_string():
    state = only(repo("panlabs-tech/panlabs", description=None))

    assert state.description is None


def test_an_observation_failure_carries_no_metadata_to_be_judged_by():
    """Nenhum item é avaliado contra um repo que não pôde ser observado."""
    state = only({"name": "panlabs-tech/instavel", "error": "HTTP 401: bad credentials"})

    assert state.error == "HTTP 401: bad credentials"
    assert state.files == frozenset()
    assert state.description is None


# --- puro, e sem rede ----------------------------------------------------------


def test_building_the_observed_state_from_a_snapshot_reaches_no_api(
    monkeypatch: pytest.MonkeyPatch,
):
    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("a observação chamou a API ao ler um retrato salvo")

    monkeypatch.setattr(gh, "api", explode)
    monkeypatch.setattr(gh, "graphql", explode)
    monkeypatch.setattr(gh, "repo_names", explode)

    state = build_observed(json.loads(FLEET.read_text(encoding="utf-8")))

    assert state.org == "panlabs-tech"
    assert state.repos


def test_the_versioned_fleet_snapshot_carries_the_whole_tree_and_the_declared_contents():
    """O retrato é fixture: é ele que mantém o planner puro e testável sem rede."""
    state = build_observed(json.loads(FLEET.read_text(encoding="utf-8")))
    by_name = {entry.name: entry for entry in state.repos}

    tfbox = by_name["panlabs-tech/tfbox"]
    assert any("/" in path for path in tfbox.files)
    assert "node" in tfbox.surfaces
    assert any(entry.contents for entry in state.repos)
