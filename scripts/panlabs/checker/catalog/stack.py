"""Os itens de stack: cobrados por **superfície**, nunca por repositório.

Stack indexa superfícies (`ANATOMY.md`): um mesmo repositório pode ter superfície
Node e Python ao mesmo tempo, e cada uma é avaliada por si. Um repositório sem a
superfície não é avaliado pelo item, e a ausência dele ali não é deriva.

A superfície agora é lida da árvore **inteira** do repositório, e não da listagem
da raiz: um manifesto em subpasta de monorepo é superfície igual, e antes ele
fazia o item nem chegar a ser avaliado -- um item que ninguém mede e que parece
verde.

O que os itens **exigem** continua igual ao de antes de a árvore ser recursiva, e
isso é deliberado: quem decide o conteúdo do catálogo é a spec de Repo #4, e a
frota acabou de mostrar que a decisão não é óbvia. Três repositórios usam
workspace de `pnpm`, com **um** lockfile na raiz servindo `apps/web/package.json`;
o `tfbox` versiona lockfile na raiz **e** ao lado de cada manifesto. Exigir
lockfile ao lado de cada manifesto reprovaria os três primeiros; aceitar lockfile
em qualquer lugar aprovaria um repositório por causa de um lockfile perdido numa
pasta que não é a do manifesto. Nenhuma das duas é decisão deste ticket.
"""

from __future__ import annotations

from panlabs.checker.catalog.item import AnatomyItem, has_file, has_surface, stack

__all__ = ["ITEMS"]

ITEMS: tuple[AnatomyItem, ...] = (
    AnatomyItem(
        id="python-runtime-declared",
        scope=stack("python"),
        applies=has_surface("python"),
        satisfied=has_file(".python-version"),
        motivo=lambda repo: (
            f"{repo.name} tem superfície Python mas não declara versão de runtime "
            "em .python-version"
        ),
    ),
    AnatomyItem(
        id="node-lockfile-committed",
        scope=stack("node"),
        applies=has_surface("node"),
        satisfied=lambda repo: bool({"package-lock.json", "pnpm-lock.yaml"} & repo.files),
        motivo=lambda repo: (
            f"{repo.name} tem superfície Node mas não versiona lockfile "
            "(package-lock.json ou pnpm-lock.yaml)"
        ),
    ),
)
