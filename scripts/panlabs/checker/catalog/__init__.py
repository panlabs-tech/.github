"""O catálogo-semente de itens de anatomia, um módulo por eixo.

O suficiente para exercitar os três escopos de verdade (org, stack e tipo),
não o catálogo cheio -- que é da spec de Repo #4 (ver `ANATOMY.md`). Onde a
#4 decidir diferente, ela substitui os itens daqui; este pacote não antecipa
esse conteúdo além do que já está publicado e decidido.

**Um módulo por eixo, e o endereço carrega o escopo.** O catálogo cheio tem da
ordem de vinte e cinco itens em três eixos, e um arquivo único tornaria a escrita
dele uma sessão que não cabe. O vocabulário compartilhado (o tipo de um item, o
escopo, os predicados) mora em `item.py`; cada módulo de eixo carrega só os itens
dele, e um teste guarda que nenhum item mora no eixo errado.

Os módulos entram aqui **renomeados** de propósito. `item.py` exporta `stack()` e
`tipo()`, que são fábricas de escopo com exatamente os mesmos nomes dos módulos de
eixo: importar as duas coisas neste arquivo faria uma sombrear a outra em silêncio,
e o catálogo sairia vazio ou quebrado sem que nada acusasse.

A ordem do catálogo é a ordem dos eixos, e ela é estável: a matriz é comparada
entre corridas, e um plano que muda de ordem sozinho não é revisável.
"""

from __future__ import annotations

from panlabs.checker.catalog.item import ORG, AnatomyItem, Scope, ScopeKind
from panlabs.checker.catalog.org import ITEMS as ORG_ITEMS
from panlabs.checker.catalog.stack import ITEMS as STACK_ITEMS
from panlabs.checker.catalog.tipo import ITEMS as TIPO_ITEMS

__all__ = ["DEFAULT_CATALOG", "ORG", "AnatomyItem", "Scope", "ScopeKind"]

DEFAULT_CATALOG: tuple[AnatomyItem, ...] = ORG_ITEMS + STACK_ITEMS + TIPO_ITEMS
