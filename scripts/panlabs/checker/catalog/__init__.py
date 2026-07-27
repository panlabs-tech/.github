"""O catálogo de itens de anatomia, um módulo por eixo.

É o catálogo **cheio**: a lista completa de itens da [`ANATOMY.md`](../../../../ANATOMY.md),
onde antes havia uma semente de cinco itens. A propriedade que o documento e este
pacote sustentam juntos é uma só: **item escrito lá tem veredito aqui**. Um item
que existisse só em prosa seria recomendação, e a leitura binária da anatomia não
tem nível recomendado.

**Um módulo por eixo, e o endereço carrega o escopo.** São da ordem de trinta itens
em três eixos, e um arquivo único tornaria a escrita e a revisão deles uma sessão
que não cabe. O vocabulário compartilhado (o tipo de um item, o escopo, os
predicados) mora em `item.py`, os caminhos que mais de um eixo pergunta moram em
`paths.py`, e cada módulo de eixo carrega só os itens dele. Um teste guarda que
nenhum item mora no eixo errado: um item de stack no módulo de org mentiria sobre
o eixo em que foi avaliado, e o escopo é o que permite auditar o próprio checker.

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
