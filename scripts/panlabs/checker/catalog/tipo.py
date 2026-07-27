"""Os itens de tipo: cobrados só da categoria que os declara.

Os cinco tipos são nomeados e finitos (`ANATOMY.md`), e o tipo de um repositório
é dado versionado em `config/repo-types.json`, nunca inferência do checker. Um
repositório ainda não classificado não é alcançado por item nenhum daqui, e isso
não é deriva: é o resultado esperado de uma classificação que ninguém fez.

**Três dos cinco tipos não declaram item nenhum, e isso é conteúdo, não lacuna.**

O módulo de infraestrutura é **variante declarada, não exceção**: ele é cobrado de
todo invariante e de todo item das superfícies que tem, e o que o distingue é ficar
fora do escopo da regra de gerenciador de pacotes do tipo aplicação. Ficar de fora
**por escopo** é diferente de ficar de fora por um `if`: o primeiro é revisável na
matriz ("este item é de tipo aplicação"), o segundo some no código.

`skills` e `dotfiles` têm stack vazia por natureza, e é justamente por não
carregarem item de superfície nenhum que são o fixture que importa: é neles que um
contrato de required checks ingênuo quebra, e é o item invariante de rollup que os
salva. Um item de tipo para eles seria inventar obrigação que ninguém decidiu.
"""

from __future__ import annotations

from panlabs.checker.catalog.item import (
    AnatomyItem,
    all_of,
    has_file,
    has_surface,
    is_tipo,
    tipo,
)
from panlabs.checker.catalog.paths import COMPOSE_FILES, MCP_CONFIG
from panlabs.checker.desired import Desired
from panlabs.checker.model import RepoObserved

__all__ = ["ITEMS"]

APPS_DIR = "apps/"

CONVERGED_LOCKFILE = "pnpm-lock.yaml"
DIVERGENT_LOCKFILES = ("package-lock.json", "yarn.lock", "bun.lockb")
"""Gerenciador de pacotes único, e a regra alcança **só** o tipo aplicação.

O levantamento do mapa registrou que apenas a vitrine usava o gerenciador
divergente. São dois: o módulo de infraestrutura também usa. Isso não muda a
decisão, porque o workflow compartilhado de checks Node aceita o gerenciador como
parâmetro e o módulo de infraestrutura não é do tipo aplicação. Muda o inventário
de retrofit, e é por isso que o item mora aqui e não em `stack.py`.
"""

ENV_EXAMPLE = ".env.example"

STATEFUL_MARKERS = ("alembic.ini", "/alembic/", "/migrations/", "drizzle.config", "prisma/schema")
"""O que faz uma aplicação ter dependência local com estado: ela migra um banco.

A composição de serviços locais é condicional, e este é o predicado da condição.
A vitrine da frota legitimamente não tem nenhum destes, e a ausência de composição
lá **não é** deriva -- é o falso positivo que a spec de Repo #4 antecipou por
escrito, e o teste que o codifica é o mais importante deste módulo.
"""


def _app_dirs(repo: RepoObserved) -> tuple[str, ...]:
    """As aplicações do monorepo, pelo prefixo `apps/<nome>/`, em ordem estável."""
    return tuple(
        sorted(
            {
                "/".join(path.split("/")[:2])
                for path in repo.files
                if path.startswith(APPS_DIR) and path.count("/") >= 2
            }
        )
    )


def _has_monorepo_layout(repo: RepoObserved, desired: Desired) -> bool:
    del desired
    return bool(_app_dirs(repo))


def _has_stateful_dependency(repo: RepoObserved, desired: Desired) -> bool:
    del desired
    return any(marker in path for path in repo.files for marker in STATEFUL_MARKERS)


def _apps_without_dockerfile(repo: RepoObserved) -> tuple[str, ...]:
    return tuple(app for app in _app_dirs(repo) if f"{app}/Dockerfile" not in repo.files)


def _why_not_converged(repo: RepoObserved, desired: Desired) -> str:
    """Nomeia o gerenciador divergente encontrado, ou a ausência de qualquer um."""
    del desired
    found = sorted(set(DIVERGENT_LOCKFILES) & repo.files)
    achado = ", ".join(found) if found else "nenhum lockfile na raiz"
    return (
        f"{repo.name} é aplicação e não converge no gerenciador de pacotes da frota: "
        f"a raiz tem {achado} em vez de {CONVERGED_LOCKFILE}"
    )


ITEMS: tuple[AnatomyItem, ...] = (
    AnatomyItem(
        id="anatomy-doc-exists",
        scope=tipo("meta"),
        applies=is_tipo("meta"),
        satisfied=has_file("ANATOMY.md"),
        motivo=lambda repo, desired: f"{repo.name} é do tipo meta mas não tem ANATOMY.md na raiz",
    ),
    AnatomyItem(
        id="app-monorepo-layout",
        scope=tipo("aplicacao"),
        applies=is_tipo("aplicacao"),
        satisfied=_has_monorepo_layout,
        motivo=lambda repo, desired: (
            f"{repo.name} é aplicação e não tem layout de monorepo com aplicações em subpastas "
            f"de {APPS_DIR}: navegar entre as aplicações da frota passa a exigir "
            "recontextualização"
        ),
    ),
    AnatomyItem(
        id="app-package-manager-single",
        scope=tipo("aplicacao"),
        # Só a aplicação com superfície Node: uma sem ela não tem gerenciador de
        # pacotes a convergir, e cobrar lockfile dela seria cobrar o que não existe.
        applies=all_of(is_tipo("aplicacao"), has_surface("node")),
        satisfied=lambda repo, desired: (
            CONVERGED_LOCKFILE in repo.files
            and not any(lock in repo.files for lock in DIVERGENT_LOCKFILES)
        ),
        motivo=_why_not_converged,
    ),
    AnatomyItem(
        id="app-container-build",
        scope=tipo("aplicacao"),
        # Só onde há layout de monorepo: sem ele, a linha a ler é a de
        # `app-monorepo-layout`, e cobrar Dockerfile por aplicação de um repositório
        # que não tem aplicações em subpasta seria cobrar sobre um conjunto vazio.
        applies=all_of(is_tipo("aplicacao"), _has_monorepo_layout),
        satisfied=lambda repo, desired: not _apps_without_dockerfile(repo),
        motivo=lambda repo, desired: (
            f"{repo.name} tem aplicação sem arquivo de build de container ao lado: "
            f"{', '.join(_apps_without_dockerfile(repo))}"
        ),
    ),
    AnatomyItem(
        id="app-mcp-config-versioned",
        scope=tipo("aplicacao"),
        applies=is_tipo("aplicacao"),
        satisfied=has_file(MCP_CONFIG),
        motivo=lambda repo, desired: (
            f"{repo.name} é aplicação e não versiona {MCP_CONFIG} com placeholder de variável "
            "de ambiente: hoje a configuração real fica gitignorada com segredo literal dentro, "
            "e nunca é de fato compartilhada apesar do nome"
        ),
    ),
    AnatomyItem(
        id="app-env-example",
        scope=tipo("aplicacao"),
        applies=is_tipo("aplicacao"),
        satisfied=has_file(ENV_EXAMPLE),
        motivo=lambda repo, desired: (
            f"{repo.name} é aplicação e não tem {ENV_EXAMPLE}, então quem chega não sabe o que "
            "precisa preencher sem ler o código"
        ),
    ),
    AnatomyItem(
        id="app-local-services-composition",
        scope=tipo("aplicacao"),
        # Condicional de verdade: existe **se e somente se** a aplicação tem
        # dependência local com estado. A vitrine não tem, e a ausência dela lá não
        # é deriva -- é o resultado esperado.
        applies=all_of(is_tipo("aplicacao"), _has_stateful_dependency),
        satisfied=lambda repo, desired: bool(set(COMPOSE_FILES) & repo.files),
        motivo=lambda repo, desired: (
            f"{repo.name} é aplicação com dependência local com estado e não declara composição "
            f"de serviços locais ({' ou '.join(COMPOSE_FILES)})"
        ),
    ),
)
