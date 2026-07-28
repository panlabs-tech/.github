"""O documento e o executável são o mesmo catálogo, e este teste é o que amarra.

`ANATOMY.md` é a definição canônica; `scripts/panlabs/checker/catalog/` é o que a
mede. Item escrito só no documento seria **recomendação**, e a leitura binária da
anatomia não tem nível recomendado. Item que existisse só no catálogo cobraria uma
obrigação que ninguém escreveu, e a matriz reprovaria um repositório por uma regra
que não está publicada em lugar nenhum.

Os dois moram no mesmo repositório justamente para não poderem divergir sem que se
note. "Sem que se note" é o que este arquivo transforma em falha de teste.
"""

import re
from pathlib import Path

from panlabs.checker.catalog import DEFAULT_CATALOG
from panlabs.checker.config import VALID_TYPES

ANATOMY = Path(__file__).resolve().parents[1] / "ANATOMY.md"

ROW = re.compile(r"^\| `([a-z][a-z0-9-]*)` \|", re.MULTILINE)
"""A primeira coluna de uma linha de tabela do catálogo: o id do item, em crase.

Ancorada no início da linha e na primeira coluna de propósito. Um id citado no
meio de um parágrafo é prosa sobre o item, não a declaração dele, e contá-lo aqui
faria a amarra afrouxar exatamente onde ela precisa apertar.
"""

AXIS_HEADING = re.compile(r"^### Eixo (\d): ", re.MULTILINE)
"""O cabeçalho que abre cada eixo do catálogo, e o número que o identifica.

O eixo é a metade do documento que decide **a quem** o item se aplica, e era a
metade que nenhum teste via: mover uma linha do Eixo 1 para o Eixo 3 não quebrava
nada, e o escopo publicado passaria a mentir sem que a matriz mudasse.
"""

AXIS_SCOPE = {"1": "org", "2": "stack", "3": "tipo"}
"""O eixo escrito no documento, e o `scope.kind` que o catálogo dá ao mesmo item.

A ordem não é livre: o documento numera os eixos na sequência em que a anatomia os
apresenta, e `catalog.DEFAULT_CATALOG` os concatena na mesma. Este mapa é o único
lugar onde as duas convenções se encontram.
"""


def documented() -> set[str]:
    return set(ROW.findall(ANATOMY.read_text(encoding="utf-8")))


def documented_by_axis() -> dict[str, set[str]]:
    """Os ids do documento, agrupados pelo eixo sob cujo cabeçalho foram escritos.

    Corta o texto nos cabeçalhos de eixo e lê as linhas de tabela de cada fatia. O
    que vem antes do primeiro cabeçalho é prosa de abertura e não entra: as tabelas
    do catálogo moram todas debaixo de um eixo.
    """
    text = ANATOMY.read_text(encoding="utf-8")
    pieces = AXIS_HEADING.split(text)[1:]
    return {
        number: set(ROW.findall(body))
        for number, body in zip(pieces[0::2], pieces[1::2], strict=True)
    }


def test_the_document_declares_at_least_one_item_at_all():
    """Um regex que deixasse de casar faria os dois testes abaixo passarem vazios."""
    assert documented()


def test_every_item_written_in_the_document_has_a_verdict_in_the_checker():
    assert documented() - {item.id for item in DEFAULT_CATALOG} == set()


def test_every_item_the_checker_charges_is_written_in_the_document():
    assert {item.id for item in DEFAULT_CATALOG} - documented() == set()


def test_the_document_declares_all_three_axes_and_nothing_beyond_them():
    """Um quarto eixo, ou um que sumiu, quebraria o mapa sem quebrar o resto."""
    assert set(documented_by_axis()) == set(AXIS_SCOPE)


def test_every_item_is_written_under_the_axis_in_which_the_checker_evaluates_it():
    """O eixo é a metade do documento que diz **a quem** o item se aplica.

    Os dois testes acima comparam conjunto de ids, e por isso nenhum deles via
    isto: mover uma linha do Eixo 1 para o Eixo 3 mantinha os dois conjuntos
    idênticos, o checker continuava cobrando de todo repositório, e o escopo
    publicado passava a dizer que só um tipo é cobrado. O documento é a definição
    canônica, então a divergência não seria "o documento está desatualizado", seria
    a matriz reprovando repositório por uma regra publicada com outro alcance.
    """
    by_axis = documented_by_axis()
    scope_of = {item.id: item.scope.kind for item in DEFAULT_CATALOG}

    wrong = {
        item_id: (AXIS_SCOPE[number], scope_of[item_id])
        for number, ids in by_axis.items()
        for item_id in ids
        if scope_of.get(item_id) != AXIS_SCOPE[number]
    }

    assert wrong == {}


def test_the_document_names_the_five_types_by_the_value_that_is_declared():
    """Classificar um repositório novo é escolha entre os cinco, nunca invenção.

    Pelo valor declarado, e não pelo nome em prosa: é o valor que vai para
    `config/repo-types.json` e é ele que aparece no escopo de uma linha da matriz.
    Um tipo que o checker aceita e o documento não nomeia seria uma classificação
    válida que ninguém sabe existir.
    """
    text = ANATOMY.read_text(encoding="utf-8")

    for value in VALID_TYPES:
        assert f"`{value}`" in text
