"""Os itens de stack: cobrados por **superfície**, nunca por repositório.

Stack indexa superfícies (`ANATOMY.md`): um mesmo repositório pode ter superfície
Node e Python ao mesmo tempo, e cada uma é avaliada por si. Um repositório sem a
superfície não é avaliado pelo item, e a ausência dele ali não é deriva. Um
repositório sem superfície nenhuma não recebe linha nenhuma deste módulo, e é isso
que faz `skills` e `dotfiles` serem o fixture que importa em vez do caso de borda.

A superfície é lida da árvore **inteira** do repositório, e não da listagem da
raiz: um manifesto em subpasta de monorepo é superfície igual. Mas **o que cada
item exige é decisão dele**, e as duas perguntas não se confundem. Os itens de
slot de runtime perguntam pela raiz, porque é na raiz que o gerenciador de runtime
da máquina lê; os itens de ferramenta perguntam pelos manifestos declarados, porque
é neles que a ferramenta é declarada e a frota tem mais de um layout.

**Terraform tem superfície e não tem item.** Isso é resultado, não esquecimento:
Terraform como CI compartilhada está fora do escopo da spec de Repo #4, porque
existe num repositório só. A superfície continua sendo detectada, e o dia em que
houver o que cobrar dela, o item entra aqui sem que nada mais mude.
"""

from __future__ import annotations

from collections.abc import Callable

from panlabs.checker.catalog.item import (
    AnatomyItem,
    all_of,
    declared_version,
    declares,
    has_surface,
    in_series,
    job_declared,
    slot_filled,
    stack,
)
from panlabs.checker.catalog.paths import NODE_MANIFESTS, PR_CHECKS, PYTHON_MANIFESTS
from panlabs.checker.desired import Desired
from panlabs.ci.rollup import build_rollup

__all__ = ["ITEMS"]

PYTHON_VERSION = ".python-version"
NODE_VERSION = ".node-version"

PYTHON_TOOLCHAIN = ("[tool.ruff", "ruff")
"""Valor decidido, não slot: a superfície Python da frota verifica e formata com ruff.

A spec de Fundação decidiu a toolchain Python (`uv`, `ruff`, `pyright`, `pytest`), e
"está limpo" precisa significar o mesmo em qualquer repositório -- que é a razão de
o item existir. Duas formas do mesmo fato porque a declaração pode ser a seção de
configuração ou a dependência de desenvolvimento.
"""

NODE_TOOLCHAIN = ("biome", "eslint", "prettier")
"""Slot, não valor: a superfície Node declara **uma** ferramenta de formatação e lint.

Aqui a anatomia para na declaração, e de propósito: a spec de Repo #4 nomeia a
toolchain Python e não nomeia a Node, e cravar uma escolha que ninguém decidiu seria
o checker legislando em vez de medir.
"""

NODE_LOCKFILES = ("package-lock.json", "pnpm-lock.yaml")
"""O lockfile da **raiz**, e essa escolha tem um retrato por trás.

Os cinco repositórios com superfície Node usam dois layouts: três têm workspace de
`pnpm`, com um único lockfile na raiz servindo `apps/web/package.json`; o módulo de
infraestrutura versiona lockfile na raiz **e** ao lado de cada manifesto. Exigir
lockfile ao lado de cada manifesto reprovaria os três primeiros; aceitar lockfile em
qualquer lugar aprovaria um repositório por causa de um lockfile perdido numa pasta
que não é a do manifesto. O da raiz é o que todos os cinco têm.
"""


def _ci_leg(surface: str) -> str:
    """O nome da perna de checks daquela superfície, tirado do contrato do rollup.

    Vem de `build_rollup` em vez de escrito de novo: o nome que o caller precisa
    declarar é exatamente o que o rollup vai listar em `needs`, e duas cópias da
    mesma string divergiriam no dia em que uma mudasse -- com o sintoma sendo um
    PR pendurado para sempre, que é o mais difícil de diagnosticar porque não há
    erro, só espera.
    """
    return build_rollup([surface]).needs[0]


def _runtime_slot(surface: str, path: str) -> AnatomyItem:
    return AnatomyItem(
        id=f"{surface}-runtime-declared",
        scope=stack(surface),
        applies=has_surface(surface),
        satisfied=slot_filled(path),
        motivo=lambda repo, desired: (
            f"{repo.name} tem superfície {surface} e não declara versão de runtime em {path} "
            "(ausente ou vazio), que é onde o gerenciador de runtime da máquina lê"
        ),
        reads=(path,),
    )


def _converged(surface: str, path: str, series: Callable[[Desired], str | None]) -> AnatomyItem:
    """A série convergida: item que só é avaliado quando o valor foi decidido.

    O slot acima cobra que o repositório **declare**; este cobra que a frota declare
    a **mesma** coisa, porque versões diferentes fazem "verde" significar coisas
    diferentes. São perguntas distintas, e por isso itens distintos: um repositório
    pode declarar e mesmo assim divergir.

    A dimensão decidida entra como função de leitura, e não pelo nome da superfície:
    buscar `desired` por nome montado faria uma superfície nova estourar em tempo de
    execução, dentro do planner, no lugar onde nada deveria poder estourar.

    Enquanto `config/anatomy.json` trouxer `null` na dimensão, nada é avaliado. Não
    decidido não é o mesmo que decidido-como-vazio, e é o oposto de conforme.
    """
    return AnatomyItem(
        id=f"{surface}-runtime-converged",
        scope=stack(surface),
        applies=all_of(
            has_surface(surface),
            lambda repo, desired: series(desired) is not None,
            slot_filled(path),
        ),
        satisfied=lambda repo, desired: in_series(
            declared_version(repo.content(path) or ""), series(desired) or ""
        ),
        motivo=lambda repo, desired: (
            f"{repo.name} declara {declared_version(repo.content(path) or '')} em {path}, "
            f"e a frota converge para a série {series(desired)}"
        ),
        reads=(path,),
    )


def _ci_leg_item(surface: str) -> AnatomyItem:
    leg = _ci_leg(surface)
    return AnatomyItem(
        id=f"{surface}-ci-leg",
        scope=stack(surface),
        applies=has_surface(surface),
        satisfied=declares((PR_CHECKS,), (job_declared(leg),)),
        motivo=lambda repo, desired: (
            f"{repo.name} tem superfície {surface} e não declara a perna {leg} em {PR_CHECKS}: "
            "o rollup agrega o que existe, então uma perna que não está lá sai verde sem ter "
            "rodado nada"
        ),
        reads=(PR_CHECKS,),
    )


ITEMS: tuple[AnatomyItem, ...] = (
    _runtime_slot("python", PYTHON_VERSION),
    _converged("python", PYTHON_VERSION, lambda desired: desired.python_series),
    AnatomyItem(
        id="python-toolchain-declared",
        scope=stack("python"),
        applies=has_surface("python"),
        satisfied=declares(PYTHON_MANIFESTS, PYTHON_TOOLCHAIN),
        motivo=lambda repo, desired: (
            f"{repo.name} tem superfície Python e nenhum manifesto declarado "
            f"({', '.join(PYTHON_MANIFESTS)}) declara ruff, a ferramenta de formatação e "
            "verificação da superfície"
        ),
        reads=PYTHON_MANIFESTS,
    ),
    _ci_leg_item("python"),
    _runtime_slot("node", NODE_VERSION),
    _converged("node", NODE_VERSION, lambda desired: desired.node_series),
    AnatomyItem(
        id="node-lockfile-committed",
        scope=stack("node"),
        applies=has_surface("node"),
        satisfied=lambda repo, desired: bool(set(NODE_LOCKFILES) & repo.files),
        motivo=lambda repo, desired: (
            f"{repo.name} tem superfície Node mas não versiona lockfile na raiz "
            f"({' ou '.join(NODE_LOCKFILES)})"
        ),
    ),
    AnatomyItem(
        id="node-toolchain-declared",
        scope=stack("node"),
        applies=has_surface("node"),
        satisfied=declares(NODE_MANIFESTS, NODE_TOOLCHAIN),
        motivo=lambda repo, desired: (
            f"{repo.name} tem superfície Node e nenhum manifesto declarado "
            f"({', '.join(NODE_MANIFESTS)}) declara ferramenta de formatação e lint "
            f"({', '.join(NODE_TOOLCHAIN)})"
        ),
        reads=NODE_MANIFESTS,
    ),
    _ci_leg_item("node"),
)
