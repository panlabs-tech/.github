"""O vocabulário de um item de anatomia, compartilhado pelos três eixos.

Aqui não mora item nenhum: moram o tipo de um item, o escopo em que ele é
avaliado e os predicados que os três módulos de eixo reaproveitam. A separação
existe porque o catálogo cheio tem da ordem de trinta itens, e um arquivo
único faria a escrita dele não caber numa sessão.

**Todo predicado recebe `(repo, desired)`, inclusive os que ignoram o segundo.**
A uniformidade é deliberada: um item que compara contra valor decidido e um item
que não compara contra nada são a mesma coisa do ponto de vista do planner, e uma
assinatura por espécie faria o catálogo carregar duas convenções. `desired` é dado
versionado, não observação, e por isso entra como segundo argumento, igual ao que
`plan(observed, desired)` já faz no resto do repo.

**Um item que lê conteúdo declara o que lê, em `reads`.** Um caminho que ninguém
declarou em `config/checker.json` nunca chega ao estado observado, e o item sairia
com veredito tirado do vazio em vez de do repositório -- verde ou vermelho por
engano, indistinguível de um veredito real. Um teste amarra os dois lados.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from panlabs.checker.desired import Desired
from panlabs.checker.model import RepoObserved

__all__ = [
    "ORG",
    "AnatomyItem",
    "Predicate",
    "Reason",
    "Scope",
    "ScopeKind",
    "all_of",
    "always",
    "any_of",
    "declared_version",
    "declares",
    "has_any_file",
    "has_file",
    "has_path_under",
    "has_surface",
    "in_series",
    "is_tipo",
    "job_declared",
    "paths_under",
    "slot_filled",
    "stack",
    "tipo",
]

ScopeKind = Literal["org", "stack", "tipo"]

Predicate = Callable[[RepoObserved, Desired], bool]
Reason = Callable[[RepoObserved, Desired], str]


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
    que evita cobrar item de superfície Node de um repositório Terraform, e é a
    mesma que faz um documento condicional legitimamente ausente não ser deriva.

    `applies` também é onde mora a dependência entre itens do mesmo assunto: o
    item que cobra o **conteúdo** de um documento só se aplica onde o documento
    existe, porque a ausência dele já é a linha de outro item. Sem isso, um
    arquivo faltando produziria duas linhas dizendo a mesma coisa, e a matriz
    passaria a contar deriva em dobro.
    """

    id: str
    scope: Scope
    applies: Predicate
    satisfied: Predicate
    motivo: Reason
    reads: tuple[str, ...] = ()


# --- predicados de aplicação --------------------------------------------------


def always(repo: RepoObserved, desired: Desired) -> bool:
    del repo, desired
    return True


def all_of(*predicates: Predicate) -> Predicate:
    """A conjunção de predicados, para um item cuja condição tem mais de um fator."""

    def check(repo: RepoObserved, desired: Desired) -> bool:
        return all(predicate(repo, desired) for predicate in predicates)

    return check


def any_of(*predicates: Predicate) -> Predicate:
    """A disjunção de predicados, para o item que aceita mais de uma forma de satisfação.

    Existe para o caso em que a anatomia cobra o **fato** e a frota o realiza por
    caminhos diferentes: o padrão de mensagem de commit está declarado tanto por
    um arquivo de configuração do linter quanto por uma linha do portão local, e
    exigir uma das duas formas seria cravar a ferramenta em vez do fato.
    """

    def check(repo: RepoObserved, desired: Desired) -> bool:
        return any(predicate(repo, desired) for predicate in predicates)

    return check


def has_surface(surface: str) -> Predicate:
    def check(repo: RepoObserved, desired: Desired) -> bool:
        del desired
        return surface in repo.surfaces

    return check


def has_file(path: str) -> Predicate:
    """O arquivo existe na árvore, no caminho exato pedido.

    Caminho, e não nome: a observação enxerga o repositório inteiro, então
    `ANATOMY.md` é a raiz e `docs/ANATOMY.md` é outro arquivo. Um item que
    aceitasse qualquer profundidade passaria por conta de um homônimo enterrado.
    """

    def check(repo: RepoObserved, desired: Desired) -> bool:
        del desired
        return path in repo.files

    return check


def has_any_file(paths: Sequence[str]) -> Predicate:
    """Pelo menos um dos caminhos existe. Para item que aceita mais de uma forma."""

    def check(repo: RepoObserved, desired: Desired) -> bool:
        del desired
        return bool(set(paths) & repo.files)

    return check


def is_tipo(value: str) -> Predicate:
    def check(repo: RepoObserved, desired: Desired) -> bool:
        del desired
        return repo.tipo == value

    return check


# --- predicados de conteúdo ---------------------------------------------------


def slot_filled(path: str) -> Predicate:
    """O arquivo existe **e diz alguma coisa**.

    É a diferença entre os dois estados que a observação se recusa a julgar:
    ausente é `None`, vazio é `""`, e um slot só está preenchido no terceiro
    caso. Um `.python-version` vazio declara tanto quanto um que não existe, e
    a anatomia obriga a declaração, não o arquivo.
    """

    def check(repo: RepoObserved, desired: Desired) -> bool:
        del desired
        return bool((repo.content(path) or "").strip())

    return check


def declares(paths: Sequence[str], tokens: Sequence[str]) -> Predicate:
    """Algum dos arquivos declarados menciona algum dos termos.

    Vários caminhos porque a frota tem mais de um layout de manifesto, e vários
    termos porque o item costuma cobrar um **slot** (a superfície declara uma
    ferramenta de verificação) e não um valor (a superfície declara *esta*
    ferramenta). Onde a lista de termos tem um só, o item cobra valor decidido, e
    o texto do item é quem diz por quê.
    """

    def check(repo: RepoObserved, desired: Desired) -> bool:
        del desired
        return any(token in (repo.content(path) or "") for path in paths for token in tokens)

    return check


# --- predicados de árvore -----------------------------------------------------


def paths_under(repo: RepoObserved, prefixes: Iterable[str]) -> tuple[str, ...]:
    """Os caminhos versionados sob algum dos prefixos, em ordem estável.

    Devolve os caminhos, e não um booleano, porque o motivo de um item de
    ausência precisa nomear o que encontrou: "versiona equipamento global" não é
    acionável, "versiona .claude/skills/tdd/SKILL.md" é.
    """
    return tuple(sorted(path for path in repo.files if any(path.startswith(p) for p in prefixes)))


def has_path_under(prefixes: Sequence[str]) -> Predicate:
    def check(repo: RepoObserved, desired: Desired) -> bool:
        del desired
        return bool(paths_under(repo, prefixes))

    return check


def declared_version(text: str) -> str:
    """A versão declarada num arquivo de versão de runtime, normalizada.

    `3.12\\n`, `24` e `v22.14.0` são todas declarações reais, e nenhuma delas é um
    número limpo. A normalização para no `v` e no espaço em branco de propósito:
    ela arruma o que a frota escreve, não interpreta faixa de versão.
    """
    return text.strip().lstrip("v")


def in_series(version: str, series: str) -> bool:
    """A versão declarada pertence à série decidida.

    **Série, e não major**, porque as duas superfícies medem convergência em
    unidades diferentes: em Node a série é o major (`24` cobre `24.3.0`), e em
    Python a unidade em que "verde significa o mesmo" é `3.12`, já que `3.12` e
    `3.13` divergem em comportamento de biblioteca. Uma regra só serve às duas,
    porque a série é o prefixo: `3.12` aceita `3.12.4` e recusa `3.13`.
    """
    return version == series or version.startswith(f"{series}.")


def job_declared(job: str) -> str:
    """O trecho que declara um job de nome fixo num workflow.

    Dois espaços porque é a indentação de job em todo caller da frota, e a âncora
    de quebra de linha é o que impede um `needs:` que **menciona** o nome de
    passar por uma declaração dele. É casamento de texto, não parse de YAML: a
    alternativa custaria uma dependência para ler um arquivo que a observação já
    trouxe como string, e o que se verifica aqui é presença de contrato, não
    validade de YAML -- essa a própria plataforma cobra.
    """
    return f"\n  {job}:"
