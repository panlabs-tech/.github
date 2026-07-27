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


def documented() -> set[str]:
    return set(ROW.findall(ANATOMY.read_text(encoding="utf-8")))


def test_the_document_declares_at_least_one_item_at_all():
    """Um regex que deixasse de casar faria os dois testes abaixo passarem vazios."""
    assert documented()


def test_every_item_written_in_the_document_has_a_verdict_in_the_checker():
    assert documented() - {item.id for item in DEFAULT_CATALOG} == set()


def test_every_item_the_checker_charges_is_written_in_the_document():
    assert {item.id for item in DEFAULT_CATALOG} - documented() == set()


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
