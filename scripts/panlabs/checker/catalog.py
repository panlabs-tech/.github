"""O catálogo-semente de itens de anatomia.

O suficiente para exercitar os três escopos de verdade (org, stack e tipo),
não o catálogo cheio -- que é da spec de Repo #4 (ver `ANATOMY.md`). Onde a
#4 decidir diferente, ela substitui os itens daqui; este módulo não antecipa
esse conteúdo além do que já está publicado e decidido.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from panlabs.checker.model import RepoObserved

__all__ = ["DEFAULT_CATALOG", "AnatomyItem", "Scope"]

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


def _always(repo: RepoObserved) -> bool:
    del repo
    return True


def _has_surface(surface: str) -> Callable[[RepoObserved], bool]:
    def check(repo: RepoObserved) -> bool:
        return surface in repo.surfaces

    return check


def _has_file(name: str) -> Callable[[RepoObserved], bool]:
    def check(repo: RepoObserved) -> bool:
        return name in repo.files

    return check


def _is_tipo(value: str) -> Callable[[RepoObserved], bool]:
    def check(repo: RepoObserved) -> bool:
        return repo.tipo == value

    return check


DEFAULT_CATALOG: tuple[AnatomyItem, ...] = (
    AnatomyItem(
        id="readme-exists",
        scope=ORG,
        applies=_always,
        satisfied=lambda repo: repo.has_readme,
        motivo=lambda repo: f"{repo.name} não tem README",
    ),
    AnatomyItem(
        id="license-exists",
        scope=ORG,
        applies=_always,
        satisfied=lambda repo: repo.has_license,
        motivo=lambda repo: f"{repo.name} não tem LICENSE",
    ),
    AnatomyItem(
        id="python-runtime-declared",
        scope=stack("python"),
        applies=_has_surface("python"),
        satisfied=_has_file(".python-version"),
        motivo=lambda repo: (
            f"{repo.name} tem superfície Python mas não declara versão de runtime "
            "em .python-version"
        ),
    ),
    AnatomyItem(
        id="node-lockfile-committed",
        scope=stack("node"),
        applies=_has_surface("node"),
        satisfied=lambda repo: bool({"package-lock.json", "pnpm-lock.yaml"} & repo.files),
        motivo=lambda repo: (
            f"{repo.name} tem superfície Node mas não versiona lockfile "
            "(package-lock.json ou pnpm-lock.yaml)"
        ),
    ),
    AnatomyItem(
        id="anatomy-doc-exists",
        scope=tipo("meta"),
        applies=_is_tipo("meta"),
        satisfied=_has_file("ANATOMY.md"),
        motivo=lambda repo: f"{repo.name} é do tipo meta mas não tem ANATOMY.md na raiz",
    ),
)
