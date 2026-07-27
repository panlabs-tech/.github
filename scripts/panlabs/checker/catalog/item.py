"""O vocabulário de um item de anatomia, compartilhado pelos três eixos.

Aqui não mora item nenhum: moram o tipo de um item, o escopo em que ele é
avaliado e os predicados que os três módulos de eixo reaproveitam. A separação
existe porque o catálogo cheio tem da ordem de vinte e cinco itens, e um arquivo
único faria a escrita dele não caber numa sessão.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from panlabs.checker.model import RepoObserved

__all__ = [
    "ORG",
    "AnatomyItem",
    "Scope",
    "ScopeKind",
    "always",
    "has_file",
    "has_surface",
    "is_tipo",
    "stack",
    "tipo",
]

ScopeKind = Literal["org", "stack", "tipo"]


@dataclass(frozen=True)
class Scope:
    """O eixo em que um item foi avaliado, e o valor dentro dele quando houver.

    Obrigatório em cada linha da matriz: é o que permite auditar o próprio
    checker. "Reprovou por item de stack Node" é revisável; "reprovou" não é.
    """

    kind: ScopeKind
    value: str | None = None

    def describe(self) -> str:
        if self.kind == "org":
            return "invariante de org"
        return f"{self.kind} {self.value}"


ORG = Scope(kind="org")


def stack(value: str) -> Scope:
    return Scope(kind="stack", value=value)


def tipo(value: str) -> Scope:
    return Scope(kind="tipo", value=value)


@dataclass(frozen=True)
class AnatomyItem:
    """Um item da anatomia: a que escopo pertence, quando se aplica, o que exige.

    `applies` decide se o item entra em jogo para o repositório. Um item de
    escopo stack cujo `applies` devolve falso não é avaliado, e portanto não
    gera linha nenhuma -- nem de conformidade, nem de deriva. É essa distinção
    que evita cobrar item de superfície Node de um repositório Terraform.
    """

    id: str
    scope: Scope
    applies: Callable[[RepoObserved], bool]
    satisfied: Callable[[RepoObserved], bool]
    motivo: Callable[[RepoObserved], str]


def always(repo: RepoObserved) -> bool:
    del repo
    return True


def has_surface(surface: str) -> Callable[[RepoObserved], bool]:
    def check(repo: RepoObserved) -> bool:
        return surface in repo.surfaces

    return check


def has_file(path: str) -> Callable[[RepoObserved], bool]:
    """O arquivo existe na árvore, no caminho exato pedido.

    Caminho, e não nome: a observação enxerga o repositório inteiro, então
    `ANATOMY.md` é a raiz e `docs/ANATOMY.md` é outro arquivo. Um item que
    aceitasse qualquer profundidade passaria por conta de um homônimo enterrado.
    """

    def check(repo: RepoObserved) -> bool:
        return path in repo.files

    return check


def is_tipo(value: str) -> Callable[[RepoObserved], bool]:
    def check(repo: RepoObserved) -> bool:
        return repo.tipo == value

    return check
