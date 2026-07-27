"""O catálogo da anatomia, um módulo por eixo.

**Um módulo por eixo, e o endereço carrega o escopo.** O catálogo cheio tem da
ordem de trinta itens em três eixos, e um arquivo único tornaria a escrita dele
uma sessão que não cabe. O vocabulário compartilhado (o tipo de um item, o escopo,
os predicados) mora em `item.py`; cada módulo de eixo carrega só os itens dele, e
um teste guarda que nenhum item mora no eixo errado.

Os módulos entram aqui **renomeados** de propósito. `item.py` exporta `stack()` e
`tipo()`, que são fábricas de escopo com exatamente os mesmos nomes dos módulos de
eixo: importar as duas coisas neste arquivo faria uma sombrear a outra em silêncio,
e o catálogo sairia vazio ou quebrado sem que nada acusasse.

**O catálogo é construído, não é constante.** Cada eixo recebe o dado que os seus
itens cobram (`config/anatomy.json`, mais `config/org.json` para o que a spec de
Org já decidiu) e devolve os itens já fechados sobre esse valor. Um catálogo
constante teria de ler arquivo em tempo de import, o que faria um teste depender
do disco para existir; e cravar o valor no código apagaria a distinção entre "que
item existe" (decisão do catálogo) e "qual valor ele cobra" (dado versionado).

A ordem do catálogo é a ordem dos eixos, e ela é estável: a matriz é comparada
entre corridas, e um plano que muda de ordem sozinho não é revisável.
"""

from __future__ import annotations

from panlabs.checker.catalog.item import ORG, AnatomyItem, Scope, ScopeKind
from panlabs.checker.catalog.org import items as org_items
from panlabs.checker.catalog.stack import items as stack_items
from panlabs.checker.catalog.tipo import items as tipo_items
from panlabs.checker.config import Anatomy, load_anatomy
from panlabs.org.config import Desired, load_desired

__all__ = ["ORG", "AnatomyItem", "Scope", "ScopeKind", "build", "load_catalog"]


def build(anatomy: Anatomy, desired: Desired) -> tuple[AnatomyItem, ...]:
    """Os itens dos três eixos, concatenados na ordem dos eixos. Puro."""
    return org_items(anatomy, desired) + stack_items(anatomy) + tipo_items(anatomy)


def load_catalog() -> tuple[AnatomyItem, ...]:
    """O catálogo com o dado versionado deste repositório. Toca o disco, e só ele."""
    return build(load_anatomy(), load_desired())
