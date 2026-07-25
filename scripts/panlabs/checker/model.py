"""O estado observado da frota, no recorte que o checker de conformidade enxerga.

O seam declara `observed = { repo, tipo, superfícies[], arquivos[], metadados_gh }`
por repositório. Nada aqui decide: são fatos lidos da plataforma.

Três coisas mudam a natureza do que "arquivos" significa, e valem explicação:

**`files` é a árvore inteira, em caminho relativo à raiz.** A listagem da raiz
deixava um item de superfície em subpasta de monorepo **sem ser avaliado**, o que
é pior do que um falso positivo: é um item que ninguém mede e que parece verde.

**`contents` é o conteúdo de um conjunto declarado**, e não da árvore inteira.
Item de slot não se verifica por presença de arquivo, e ler tudo pagaria uma
chamada por arquivo. Um arquivo declarado que o repositório não tem simplesmente
não aparece aqui, e ausente é diferente de vazio.

**Descrição, topics, wiki e licença são estado observado como qualquer outro.**
Nenhum deles mora no working tree, e sem o checker eles ficariam sem vigia nenhum:
a fronteira de *verificação* com a spec de Org atravessa a de *decisão* de propósito.

`error` é o canal de alarme do próprio checker: quando a observação de um
repositório falha (rede, credencial, 404, árvore truncada), nenhum item do
catálogo é avaliado contra ele -- a falha vira um veredito de erro em vez de se
disfarçar de deriva de anatomia.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

__all__ = ["Observed", "RepoObserved"]


@dataclass(frozen=True)
class RepoObserved:
    """Um repositório da frota, no recorte que a anatomia avalia."""

    name: str
    tipo: str | None = None
    surfaces: frozenset[str] = frozenset()
    files: frozenset[str] = frozenset()
    contents: Mapping[str, str] = field(default_factory=dict)
    has_readme: bool = False
    has_license: bool = False
    description: str | None = None
    topics: frozenset[str] = frozenset()
    has_wiki: bool = False
    license: str | None = None
    error: str | None = None

    @property
    def basenames(self) -> frozenset[str]:
        """Os nomes de arquivo da árvore, sem o caminho até eles.

        Existe porque parte da anatomia é sobre o arquivo existir **em algum
        lugar** (o lockfile de um monorepo mora junto do manifesto, não na raiz)
        e parte é sobre ele existir num caminho exato (a declaração de runtime
        que o gerenciador da máquina lê está na raiz do repositório). Um item
        escolhe qual das duas pergunta faz, e o escopo dele fica revisável.
        """
        return frozenset(path.rsplit("/", 1)[-1] for path in self.files)

    def content(self, path: str) -> str | None:
        """O conteúdo de um arquivo declarado, ou `None` se ele não está lá.

        `None` é "não veio": ou ninguém declarou este caminho para leitura, ou o
        repositório não tem o arquivo. Nenhum dos dois é string vazia, que é um
        arquivo que existe e não diz nada -- e um item de slot vazio depende
        exatamente dessa diferença.
        """
        return self.contents.get(path)


@dataclass(frozen=True)
class Observed:
    """A frota como ela está agora. A lista vem da org viva, nunca de constante."""

    org: str
    repos: tuple[RepoObserved, ...] = ()

    def sorted_repos(self) -> Sequence[RepoObserved]:
        return sorted(self.repos, key=lambda r: r.name)
