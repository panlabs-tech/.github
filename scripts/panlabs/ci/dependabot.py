"""Dependabot version updates com auto-merge no verde, major sempre de fora.

Sem auto-merge, o aproveitamento medido na própria org foi de **17%**: 46 PRs de
atualização, 8 mergeados, 28 fechados, 10 parados. Um PR de rotina que espera
decisão humana não é revisão, é fila. Com auto-merge, um bump minor ou patch
aterrissa sozinho assim que os checks ficam verdes; um bump major nunca aterrissa
sozinho, porque quebra de contrato é exatamente onde o olho humano ainda paga.

Este módulo carrega a decisão em Python puro, e o workflow a repete em YAML. As
duas cópias precisam mudar juntas, do mesmo jeito que `rollup_conclusion` e o
passo em bash que a espelha: é o preço de a plataforma não deixar a decisão ser
importada de um lugar só.

O que **não** mora aqui: que o `--auto` do `gh` espera o verde, que o Dependabot
assina os próprios commits, que ligar auto-merge duas vezes no mesmo PR é
inofensivo. São fatos da plataforma, verificados no mapeamento, não código nosso.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from fnmatch import fnmatchcase
from typing import Any

__all__ = [
    "AUTO_MERGED_UPDATE_TYPES",
    "AUTO_MERGE_JOB",
    "AUTO_MERGE_WORKFLOW",
    "BRANCH_PREFIX",
    "DEPENDABOT_ACTOR",
    "MERGE_METHOD",
    "SEMVER_MAJOR",
    "SEMVER_MINOR",
    "SEMVER_PATCH",
    "automerges",
    "covers_dependabot_branches",
    "duplicate_targets",
    "update_targets",
]

DEPENDABOT_ACTOR = "dependabot[bot]"
"""O login do bot. Nada fora dele entra nesta automação."""

AUTO_MERGE_WORKFLOW = "dependabot-auto-merge.yml"
"""O reusable workflow do auto-merge, em `.github/workflows/`."""

AUTO_MERGE_JOB = "dependabot-auto-merge"
"""O id do job que o chama, no caller de cada consumidor."""

MERGE_METHOD = "squash"
"""O único método que o gate permite, e por isso o único que a automação pede.

Não é preferência: sob squash-only quem assina o commit que aterrissa na branch
protegida é o GitHub, no merge via API. Pedir merge-commit ou rebase aqui seria
recusado pela API, e o PR do Dependabot ficaria parado sem motivo visível.
"""

SEMVER_MAJOR = "version-update:semver-major"
SEMVER_MINOR = "version-update:semver-minor"
SEMVER_PATCH = "version-update:semver-patch"

AUTO_MERGED_UPDATE_TYPES = frozenset({SEMVER_MINOR, SEMVER_PATCH})
"""Os tipos de bump que aterrissam sozinhos. Fechado por construção: o que não
está aqui espera humano, inclusive um tipo que ninguém previu."""

BRANCH_PREFIX = "dependabot/"
"""A raiz do nome de branch do Dependabot, que não é configurável."""

EXAMPLE_BRANCHES = (
    f"{BRANCH_PREFIX}github_actions/actions/checkout-8.0.0",
    f"{BRANCH_PREFIX}uv/dev-dependencies-6f0d1a2b3c",
)
"""Branches reais o bastante para exercitar um filtro: uma por ecossistema
declarado, incluindo a forma agrupada, que tem mais um nível de barra."""

DEFAULT_DIRECTORY = "/"
"""Onde uma entrada sem diretório declarado aterrissa, como o Dependabot a lê."""


def automerges(author: str, update_type: str) -> bool:
    """Diz se este PR aterrissa sozinho no verde.

    Espelha, um a um, os dois `if` de `.github/workflows/dependabot-auto-merge.yml`:
    o do job, sobre o autor do PR, e o do passo de merge, sobre o tipo de bump.

    `author` é o autor do PR (`github.event.pull_request.user.login`), e não
    quem disparou o evento (`github.actor`). Os dois divergem, e é o autor que
    sustenta a garantia: um PR de terceiro não passa a ser do Dependabot porque
    o bot mexeu nele depois.

    Falso para qualquer tipo desconhecido: um bump que a regra não reconhece
    espera humano, em vez de virar minor por descuido.

    Num PR agrupado, o tipo que chega aqui é o **maior** do grupo. É o que faria
    um grupo que misturasse major com minor travar inteiro, e é a razão de a
    configuração entregue separar os dois em grupos diferentes.
    """
    return author == DEPENDABOT_ACTOR and update_type in AUTO_MERGED_UPDATE_TYPES


def update_targets(updates: Iterable[Mapping[str, Any]]) -> tuple[tuple[str, str], ...]:
    """Os pares (ecossistema, diretório) que esta configuração declara.

    `directory` e `directories` são a mesma dimensão em duas formas, e por isso
    são lidas para o mesmo par: é misturando as duas que uma duplicata entraria
    sem parecer duplicata na leitura do arquivo.
    """
    targets: list[tuple[str, str]] = []
    for update in updates:
        ecosystem = update.get("package-ecosystem") or ""
        directories = update.get("directories") or [update.get("directory") or DEFAULT_DIRECTORY]
        targets.extend((ecosystem, directory) for directory in directories)
    return tuple(targets)


def duplicate_targets(updates: Iterable[Mapping[str, Any]]) -> tuple[tuple[str, str], ...]:
    """Os alvos declarados mais de uma vez, cada um nomeado uma vez só.

    Alvo repetido é a única forma de a **configuração** duplicar PR: o mesmo
    manifesto seria avaliado duas vezes, e o mesmo bump viraria dois PRs, quando
    o GitHub não recusa o arquivo inteiro antes disso. É o que sustenta rodar a
    configuração de novo sem medo.
    """
    seen: set[tuple[str, str]] = set()
    duplicated: list[tuple[str, str]] = []
    for target in update_targets(updates):
        if target in seen and target not in duplicated:
            duplicated.append(target)
        seen.add(target)
    return tuple(duplicated)


def covers_dependabot_branches(patterns: Iterable[str]) -> bool:
    """Diz se estes filtros de branch alcançam as branches que o Dependabot empurra.

    A falha mais silenciosa deste desenho inteiro: um workflow de checks que não
    lista a raiz `dependabot/` simplesmente não roda no PR do bot. Os required
    checks nunca saem, o auto-merge espera para sempre um status que ninguém vai
    publicar, e tudo o mais parece configurado.
    """
    filters = tuple(patterns)
    return all(
        any(fnmatchcase(branch, pattern) for pattern in filters) for branch in EXAMPLE_BRANCHES
    )
