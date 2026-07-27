"""O vocabulário de um item de anatomia, compartilhado pelos três eixos.

Aqui não mora item nenhum: moram o tipo de um item, o escopo em que ele é
avaliado e os predicados que os três módulos de eixo reaproveitam. A separação
existe porque o catálogo cheio tem da ordem de trinta itens, e um arquivo
único faria a escrita dele não caber numa sessão.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from panlabs.checker.config import PathRule
from panlabs.checker.model import RepoObserved

__all__ = [
    "ORG",
    "AnatomyItem",
    "Scope",
    "ScopeKind",
    "always",
    "apps_of",
    "declared",
    "has_file",
    "has_surface",
    "is_tipo",
    "listed",
    "matches_any",
    "missing",
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


def missing(repo: RepoObserved, paths: Sequence[str]) -> tuple[str, ...]:
    """Os caminhos pedidos que a árvore não tem, em ordem estável.

    Devolve a lista, e não um booleano, porque o motivo de uma linha da matriz
    precisa **nomear** o que falta: "faltam documentos obrigatórios" manda o
    operador procurar, "falta `docs/agents/domain.md`" manda ele escrever.
    """
    return tuple(path for path in paths if path not in repo.files)


def matches_any(repo: RepoObserved, rules: Sequence[PathRule]) -> tuple[tuple[str, PathRule], ...]:
    """Os caminhos da árvore que casam com alguma regra proibida, com a regra.

    A regra viaja junto porque é ela que carrega o motivo, e um caminho sem o
    motivo dele não explica nada a quem lê a matriz.
    """
    hits: list[tuple[str, PathRule]] = []
    for path in sorted(repo.files):
        for rule in rules:
            if rule.matches(path):
                hits.append((path, rule))
                break
    return tuple(hits)


def declared(repo: RepoObserved, path: str) -> bool:
    """O arquivo existe **e diz alguma coisa**: o slot está preenchido.

    Ausente, vazio e preenchido são três estados, e um slot só passa no terceiro.
    A observação não julga nenhum dos três (`RepoObserved.content`); quem julga é
    o item, e é aqui que ele julga.
    """
    content = repo.content(path)
    return content is not None and bool(content.strip())


def listed(repo: RepoObserved, paths: Sequence[str]) -> tuple[str, ...]:
    """Os caminhos pedidos que a árvore **tem**. O espelho de `missing`."""
    return tuple(path for path in paths if path in repo.files)


def apps_of(repo: RepoObserved, apps_dir: str) -> tuple[str, ...]:
    """As aplicações do monorepo, pelo primeiro segmento sob o diretório de apps.

    O layout é o que a anatomia cobra do tipo aplicação, e é por ele que os itens
    de container e de composição de serviços encontram cada aplicação. Um repo
    com o código plano na raiz devolve vazio, que é o próprio sintoma.
    """
    prefix = apps_dir if apps_dir.endswith("/") else f"{apps_dir}/"
    names = {
        path[len(prefix) :].split("/", 1)[0]
        for path in repo.files
        if path.startswith(prefix) and "/" in path[len(prefix) :]
    }
    return tuple(sorted(name for name in names if name))
