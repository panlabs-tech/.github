"""O repo que define a anatomia é medido por ela, e o teste roda sobre esta árvore.

Nenhum teste afirmava isto. `tests/fixtures/checker-fleet-2026-07-27.json` é um
retrato correto, e nele o meta reprova em dois itens, porque foi capturado antes de
o portão local aterrissar. Um retrato datado não envelhece bem como guarda: ele
continua verdadeiro sobre o dia dele para sempre, e é exatamente por isso que não
pega o que muda depois.

O que este arquivo mede é a **metade que mora no working tree**: árvore e conteúdo
de arquivo, que é a metade que um PR pode quebrar e a única que existe antes do
merge. A outra metade (descrição, topics, wiki, visibilidade) só existe na
plataforma, e por isso entra aqui como um pano de fundo conforme, declarado e
nomeado. Quem mede aquela metade é o `panlabs-checker` contra a org viva, no passo
do heartbeat.

A leitura honesta do que passa aqui é: *dado que a plataforma está conforme, a
árvore deste commit satisfaz a anatomia inteira.* Não é "o meta está conforme": é
a parte dessa frase que um teste pode saber sozinho.
"""

from pathlib import Path
from typing import Any

from panlabs.checker import planner
from panlabs.checker.config import load_read_files
from panlabs.checker.model import Observed, RepoObserved
from panlabs.checker.observe import build_observed

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_NAME = "panlabs-tech/.github"

IGNORED = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}
"""O que não é árvore versionada. A observação real lê a árvore que o GitHub serve,
e aqui a aproximação é o disco menos o que nenhum repositório versiona."""

PLATFORM_BACKDROP: dict[str, Any] = {
    "description": "o padrão panlabs, e os mecanismos que o aplicam",
    "topics": ["python"],
    "has_wiki": False,
    "license": "MIT",
    "private": False,
}
"""As quatro dimensões que não moram no working tree, fixadas conformes.

Cravá-las não é medi-las, e é por isso que elas estão num lugar só, com nome. Um
teste que as afirmasse como observação estaria mentindo; um que as omitisse faria o
meta reprovar aqui por algo que nenhum commit pode consertar.
"""


def tree() -> frozenset[str]:
    """Os caminhos versionados desta árvore, relativos à raiz do repositório."""
    return frozenset(
        str(path.relative_to(REPO_ROOT))
        for path in REPO_ROOT.rglob("*")
        if path.is_file() and not IGNORED & set(path.relative_to(REPO_ROOT).parts)
    )


def meta_from_disk() -> RepoObserved:
    """O repo meta como a observação o veria, com a árvore e os conteúdos daqui.

    Passa pelo `build_observed` de verdade, e não monta o `RepoObserved` à mão: é
    ele que deriva superfície da árvore, e um teste que fizesse essa derivação por
    conta própria deixaria de ver o dia em que ela mudasse.

    Os caminhos lidos são os mesmos que `config/checker.json` declara: ler mais do
    que a observação busca faria este teste passar sobre um conteúdo que o checker
    real nunca enxerga, que é o defeito oposto do que ele existe para pegar.
    """
    files = tree()
    raw = {
        "org": "panlabs-tech",
        "repos": [
            {
                "name": REPO_NAME,
                "tipo": "meta",
                "files": sorted(files),
                "contents": {
                    path: (REPO_ROOT / path).read_text(encoding="utf-8")
                    for path in load_read_files()
                    if path in files
                },
                "has_readme": "README.md" in files,
                "has_license": "LICENSE" in files,
                **PLATFORM_BACKDROP,
            }
        ],
    }
    return build_observed(raw).repos[0]


def test_this_tree_satisfies_the_anatomy_it_publishes():
    """O repo que escreve a regra não pode ser o que a viola sem ninguém acusar.

    A matriz do meta sai vazia, e a asserção é sobre a lista inteira: um item novo
    que o meta não satisfaça aparece aqui no mesmo commit em que for escrito, e não
    daqui a uma semana no alarme do heartbeat.
    """
    the_matrix = planner.plan(Observed(org="panlabs-tech", repos=(meta_from_disk(),)))

    assert [item.payload["item"] for item in the_matrix] == []


def test_the_tree_this_test_reads_is_the_real_one():
    """Um `rglob` que deixasse de casar faria o teste acima passar sobre o vazio.

    É o mesmo risco que `test_the_document_declares_at_least_one_item_at_all` cobre
    do outro lado: uma leitura quebrada não falha, ela esvazia, e o vazio passa em
    tudo.
    """
    files = tree()

    assert "ANATOMY.md" in files
    assert "scripts/panlabs/checker/planner.py" in files
    assert len(files) > 50


def test_the_surfaces_are_read_from_the_tree_and_not_assumed():
    """O meta tem superfície Python, e a emenda da issue #8 é o que diz isso.

    Se um dia ela sumir da árvore, este teste falha antes de o eixo de stack parar
    de ser cobrado em silêncio.
    """
    assert "python" in meta_from_disk().surfaces
