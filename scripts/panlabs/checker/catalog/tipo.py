"""Os itens de tipo: cobrados só da categoria que os declara.

Os cinco tipos são nomeados e finitos (`ANATOMY.md`), e o tipo de um repositório
é dado versionado em `config/repo-types.json`, nunca inferência do checker. Um
repositório ainda não classificado não é alcançado por item nenhum daqui, e isso
não é deriva: é o resultado esperado de uma classificação que ninguém fez.

**O módulo de infraestrutura não tem item próprio, e isso é a definição dele.**
Ele é variante *declarada*, não exceção: a diferença é que ele é verificável como
qualquer outro, cobrado de todo invariante e de todo item das superfícies que ele
tem. O que não o alcança é a regra de convergência de gerenciador de pacotes, que
é do tipo aplicação -- e isso importa porque são **dois** os repositórios com o
gerenciador divergente, e não um: a vitrine, que a regra alcança, e o de
infraestrutura, que ela não alcança.

**Skills e dotfiles são o fixture mais importante do checker, não caso de borda.**
É neles que um contrato de required checks ingênuo quebra, e é por isso que o
rollup existe sempre. O item deles cobra o oposto do que se cobra de todo mundo:
que **não** haja superfície nenhuma. Um repositório destes que ganha superfície
ganhou código de produto que não é dele.
"""

from __future__ import annotations

from panlabs.checker.catalog.item import (
    AnatomyItem,
    apps_of,
    declared,
    is_tipo,
    listed,
    missing,
    tipo,
)
from panlabs.checker.config import Anatomy, Aplicacao
from panlabs.checker.model import RepoObserved

__all__ = ["items"]

APLICACAO = "aplicacao"
META = "meta"


def items(anatomy: Anatomy) -> tuple[AnatomyItem, ...]:
    built: list[AnatomyItem] = []
    built += _meta(anatomy)
    built += _aplicacao(anatomy)
    built += _empty_stack(anatomy)
    return tuple(built)


# --- meta ---------------------------------------------------------------------


def _meta(anatomy: Anatomy) -> list[AnatomyItem]:
    """O tipo meta carrega a própria definição do padrão, ao lado do checker.

    Que os dois morem juntos é o que impede a definição e o executável que a
    verifica de divergirem sem que ninguém note.
    """
    files = anatomy.meta_files
    if files is None:
        return []
    return [
        AnatomyItem(
            id="anatomy-doc-exists",
            scope=tipo(META),
            applies=is_tipo(META),
            satisfied=lambda repo: not missing(repo, files),
            motivo=lambda repo: (
                f"{repo.name} é do tipo meta mas não tem {', '.join(missing(repo, files))} "
                "na raiz: a definição do padrão mora no repositório que a aplica"
            ),
        )
    ]


# --- aplicação ----------------------------------------------------------------


def _aplicacao(anatomy: Anatomy) -> list[AnatomyItem]:
    app = anatomy.aplicacao
    if app is None:
        return []
    return [
        _package_manager(app),
        _monorepo_layout(app),
        _container_build(app),
        _local_services(app),
        _mcp_config(app),
        _env_example(app),
    ]


def _package_manager(app: Aplicacao) -> AnatomyItem:
    """Gerenciador de pacotes **único**: valor fixo, não slot.

    Slot é o que a anatomia deixa cada repositório escolher; este não é um. O
    ponto é que navegar entre aplicações não exija recontextualização, e dois
    gerenciadores são exatamente a recontextualização que a regra existe para
    matar. O valor mora no dado, mas ele é um valor só para a org toda.
    """
    return AnatomyItem(
        id="aplicacao-gerenciador-de-pacotes-unico",
        scope=tipo(APLICACAO),
        applies=lambda repo: repo.tipo == APLICACAO and "node" in repo.surfaces,
        satisfied=lambda repo: (
            app.package_manager_lockfile in repo.files and not listed(repo, app.foreign_lockfiles)
        ),
        motivo=lambda repo: _package_manager_motivo(repo, app),
    )


def _package_manager_motivo(repo: RepoObserved, app: Aplicacao) -> str:
    foreign = listed(repo, app.foreign_lockfiles)
    if foreign:
        return (
            f"{repo.name} usa gerenciador de pacotes divergente ({', '.join(foreign)}): "
            f"a org converge em {app.package_manager_lockfile}"
        )
    return (
        f"{repo.name} não versiona {app.package_manager_lockfile}: "
        "o gerenciador de pacotes da aplicação é único na org"
    )


def _monorepo_layout(app: Aplicacao) -> AnatomyItem:
    """Layout de monorepo com aplicações em subpastas.

    O repositório com o código plano na raiz é o que a spec chamou de quase-
    rewrite: a esteira o fatia em pedaços mergeáveis, e a gradualidade existe só
    na trajetória. Conforme continua sendo o checker passar inteiro.
    """
    return AnatomyItem(
        id="aplicacao-layout-de-monorepo",
        scope=tipo(APLICACAO),
        applies=is_tipo(APLICACAO),
        satisfied=lambda repo: bool(apps_of(repo, app.apps_dir)),
        motivo=lambda repo: (
            f"{repo.name} não tem aplicação nenhuma sob {app.apps_dir}: o código está plano "
            "na raiz, e navegar entre as aplicações da org exige recontextualização"
        ),
    )


def _container_build(app: Aplicacao) -> AnatomyItem:
    """Arquivo de build de container por aplicação, morando junto de cada uma.

    Só se aplica onde o layout já existe: cobrar um arquivo por aplicação de um
    repositório que ainda não tem aplicação nenhuma em subpasta produziria uma
    segunda linha que não diz nada que a do layout já não diga.
    """
    return AnatomyItem(
        id="aplicacao-build-de-container-por-app",
        scope=tipo(APLICACAO),
        applies=lambda repo: repo.tipo == APLICACAO and bool(apps_of(repo, app.apps_dir)),
        satisfied=lambda repo: not _apps_without_container(repo, app),
        motivo=lambda repo: (
            f"{repo.name} tem aplicação sem arquivo de build de container: "
            f"{', '.join(_apps_without_container(repo, app))}. Toda aplicação é implantável "
            "do mesmo jeito, e o arquivo mora junto de cada uma"
        ),
    )


def _apps_without_container(repo: RepoObserved, app: Aplicacao) -> tuple[str, ...]:
    prefix = app.apps_dir if app.apps_dir.endswith("/") else f"{app.apps_dir}/"
    return tuple(
        name
        for name in apps_of(repo, app.apps_dir)
        if f"{prefix}{name}/{app.container_build_file}" not in repo.files
    )


def _local_services(app: Aplicacao) -> AnatomyItem:
    """A composição de serviços locais é **condicional**, e este item prova isso.

    Ela existe se e somente se a aplicação tem dependência local com estado. Uma
    aplicação sem nenhum rastro dessa dependência não é alcançada pelo item, e a
    ausência da composição ali **não é** deriva: é o falso positivo que a spec
    antecipou explicitamente, e codificá-lo aqui é o que impede que ele volte.
    """
    return AnatomyItem(
        id="aplicacao-composicao-de-servicos-locais",
        scope=tipo(APLICACAO),
        applies=lambda repo: repo.tipo == APLICACAO and _has_stateful_dependency(repo, app),
        satisfied=lambda repo: bool(listed(repo, app.compose_files)),
        motivo=lambda repo: (
            f"{repo.name} tem dependência local com estado "
            f"({', '.join(_stateful_hits(repo, app))}) e não versiona composição de serviços "
            f"locais ({' ou '.join(app.compose_files)})"
        ),
    )


def _has_stateful_dependency(repo: RepoObserved, app: Aplicacao) -> bool:
    return bool(_stateful_hits(repo, app))


def _stateful_hits(repo: RepoObserved, app: Aplicacao) -> tuple[str, ...]:
    """Os rastros de dependência com estado na árvore, em ordem estável.

    Um marcador terminado em `/` casa o diretório em qualquer profundidade, porque
    a migração de uma aplicação mora dentro da pasta dela; sem barra, casa o nome
    do arquivo em qualquer profundidade, pelo mesmo motivo.
    """
    hits: list[str] = []
    for marker in app.stateful_markers:
        needle = marker if marker.endswith("/") else f"{marker}"
        for path in sorted(repo.files):
            if f"/{needle}" in f"/{path}" and needle not in hits:
                hits.append(needle)
                break
    return tuple(hits)


def _mcp_config(app: Aplicacao) -> AnatomyItem:
    """Configuração de MCP versionada, com placeholder de variável de ambiente.

    Isto corrige o padrão atual, em que a configuração real é sempre gitignorada
    com segredo literal dentro: nunca de fato compartilhada, apesar do nome. Num
    dos repositórios isso não é criar arquivo novo, é renomear o exemplo existente
    para o nome real e tirá-lo do gitignore.
    """
    return AnatomyItem(
        id="aplicacao-mcp-versionado-com-placeholder",
        scope=tipo(APLICACAO),
        applies=is_tipo(APLICACAO),
        satisfied=lambda repo: (
            declared(repo, app.mcp_config)
            and app.mcp_env_placeholder in (repo.content(app.mcp_config) or "")
        ),
        motivo=lambda repo: _mcp_motivo(repo, app),
    )


def _mcp_motivo(repo: RepoObserved, app: Aplicacao) -> str:
    if app.mcp_config not in repo.files:
        return (
            f"{repo.name} não versiona {app.mcp_config}: a configuração real fica gitignorada "
            "com segredo literal dentro, e nunca é de fato compartilhada apesar do nome"
        )
    return (
        f"{repo.name} versiona {app.mcp_config} sem placeholder de variável de ambiente "
        f"({app.mcp_env_placeholder}): o valor literal ali é segredo publicado"
    )


def _env_example(app: Aplicacao) -> AnatomyItem:
    return AnatomyItem(
        id="aplicacao-exemplo-de-variaveis-de-ambiente",
        scope=tipo(APLICACAO),
        applies=is_tipo(APLICACAO),
        satisfied=lambda repo: app.env_example in repo.files,
        motivo=lambda repo: (
            f"{repo.name} não versiona {app.env_example}: sem ele, o placeholder da "
            "configuração de MCP não diz que variável preencher"
        ),
    )


# --- os tipos de stack vazia --------------------------------------------------


def _empty_stack(anatomy: Anatomy) -> list[AnatomyItem]:
    types = anatomy.empty_stack_types
    if types is None:
        return []
    return [
        AnatomyItem(
            id=f"{value}-sem-superficie",
            scope=tipo(value),
            applies=is_tipo(value),
            satisfied=lambda repo: not repo.surfaces,
            motivo=lambda repo, v=value: (
                f"{repo.name} é do tipo {v}, que tem stack vazia por natureza, e ganhou "
                f"superfície {', '.join(sorted(repo.surfaces))}: isso é código de produto, "
                "que não é o conteúdo deste tipo"
            ),
        )
        for value in types
    ]
