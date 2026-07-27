"""Os itens de stack: cobrados por **superfície**, nunca por repositório.

Stack indexa superfícies (`ANATOMY.md`): um mesmo repositório pode ter superfície
Node e Python ao mesmo tempo, e cada uma é avaliada por si. Um repositório sem a
superfície não é avaliado pelo item, e a ausência dele ali não é deriva.

A superfície é lida da árvore **inteira** do repositório, e não da listagem da
raiz: um manifesto em subpasta de monorepo é superfície igual, e antes ele fazia
o item nem chegar a ser avaliado -- um item que ninguém mede e que parece verde.

**Os itens são gerados a partir do dado, um conjunto por superfície declarada.**
Não é economia de digitação: é o que garante que uma superfície nova entre no
catálogo pelo dado, com o mesmo conjunto de cobranças que as outras, em vez de
alguém precisar lembrar de escrever quatro itens à mão e esquecer um.

**A superfície Terraform não aparece aqui, e a ausência é deliberada.** Ela existe
em um repositório só, e a spec de Fundação a deixou fora da CI compartilhada
porque um reusable workflow de um consumidor é abstração sem retorno. Sem CI
compartilhada e sem ferramenta decidida, não existe item de anatomia para ela --
e não ter item é honesto, enquanto inventar um seria cobrar regra que ninguém
decidiu.

**O que os itens exigem de lockfile continua sendo o da raiz**, e isso é escolha.
A frota usa três layouts sob a mesma superfície: workspace de `pnpm`, com um
lockfile na raiz servindo `apps/web/package.json`; lockfile na raiz **e** ao lado
de cada manifesto; e manifesto único na raiz, sem subpasta nenhuma. Exigir
lockfile ao lado de cada manifesto reprovaria o primeiro layout; aceitar lockfile
em qualquer lugar aprovaria um repositório por causa de um lockfile perdido numa
pasta que não é a do manifesto. O da raiz é o único que os três layouts têm.
"""

from __future__ import annotations

from panlabs.checker.catalog.item import AnatomyItem, has_file, has_surface, stack
from panlabs.checker.config import Anatomy, Surface
from panlabs.checker.model import RepoObserved

__all__ = ["items"]


def items(anatomy: Anatomy) -> tuple[AnatomyItem, ...]:
    """Um conjunto de itens por superfície declarada, na ordem do dado."""
    surfaces = anatomy.surfaces
    if surfaces is None:
        return ()

    built: list[AnatomyItem] = []
    for surface in surfaces.values():
        built += _runtime(surface)
        built += _lockfile(surface)
        built += _local_gate(anatomy, surface)
        built += _ci_leg(anatomy, surface)
    return tuple(built)


def _runtime(surface: Surface) -> list[AnatomyItem]:
    """A versão de runtime é **slot**: obriga a declaração, não o número.

    O segundo item é a convergência da frota, e ele só existe quando o dado diz
    para qual versão maior ela converge. Enquanto isso for `null`, o item não
    avalia nada: versões diferentes fazem "verde" significar coisas diferentes,
    mas escolher qual é a versão da frota é decisão do operador, e um checker que
    a inventasse estaria cobrando regra que ninguém decidiu.
    """
    built = [
        AnatomyItem(
            id=f"{surface.name}-runtime-declared",
            scope=stack(surface.name),
            applies=has_surface(surface.name),
            satisfied=has_file(surface.runtime_file),
            motivo=lambda repo, s=surface: (
                f"{repo.name} tem superfície {s.name} mas não declara versão de runtime "
                f"em {s.runtime_file}"
            ),
        )
    ]

    major = surface.runtime_major
    if major is not None:
        built.append(
            AnatomyItem(
                id=f"{surface.name}-runtime-major-convergido",
                scope=stack(surface.name),
                applies=lambda repo, s=surface: (
                    s.name in repo.surfaces and s.runtime_file in repo.files
                ),
                satisfied=lambda repo, s=surface, m=major: _major_of(repo, s) == m,
                motivo=lambda repo, s=surface, m=major: (
                    f"{repo.name} declara runtime {s.name} {_major_of(repo, s) or 'ilegível'} "
                    f"em {s.runtime_file}, e a frota converge em {m}: versões diferentes fazem "
                    "'verde' significar coisas diferentes entre repositórios"
                ),
            )
        )
    return built


def _major_of(repo: RepoObserved, surface: Surface) -> str | None:
    """A versão maior declarada no slot, lida do valor e nunca cravada."""
    content = (repo.content(surface.runtime_file) or "").strip()
    return content.split(".", 1)[0] if content else None


def _lockfile(surface: Surface) -> list[AnatomyItem]:
    """O lockfile da superfície, quando ela tem um formato decidido.

    Uma superfície com `lockfiles: null` não é cobrada: não existe decisão sobre
    o que ela deveria versionar, e cobrar de qualquer jeito seria inventar regra.
    """
    lockfiles = surface.lockfiles
    if lockfiles is None:
        return []
    return [
        AnatomyItem(
            id=f"{surface.name}-lockfile-committed",
            scope=stack(surface.name),
            applies=has_surface(surface.name),
            satisfied=lambda repo, lf=frozenset(lockfiles): bool(lf & repo.files),
            motivo=lambda repo, s=surface, lf=tuple(lockfiles): (
                f"{repo.name} tem superfície {s.name} mas não versiona lockfile na raiz "
                f"({' ou '.join(lf)})"
            ),
        )
    ]


def _local_gate(anatomy: Anatomy, surface: Surface) -> list[AnatomyItem]:
    """O portão local roda a ferramenta **daquela** superfície.

    O invariante de org cobra que o portão exista e que ele carregue a disciplina
    de versionamento; aqui se cobra o que ele roda por superfície, que é o que faz
    "está limpo" significar a mesma coisa em qualquer repositório da org.
    """
    gate = anatomy.local_gate
    if gate is None:
        return []
    return [
        AnatomyItem(
            id=f"{surface.name}-portao-local-declara-ferramenta",
            scope=stack(surface.name),
            applies=lambda repo, s=surface, g=gate: (
                s.name in repo.surfaces and g.file in repo.files
            ),
            satisfied=lambda repo, s=surface, g=gate: s.gate_tool in (repo.content(g.file) or ""),
            motivo=lambda repo, s=surface, g=gate: (
                f"{repo.name} tem superfície {s.name} e o portão local ({g.file}) não roda "
                f"{s.gate_tool}: 'está limpo' significa coisa diferente aqui e no resto da org"
            ),
        )
    ]


def _ci_leg(anatomy: Anatomy, surface: Surface) -> list[AnatomyItem]:
    """A perna de CI daquela superfície vem do workflow compartilhado.

    O invariante de org cobra que a CI referencie os workflows compartilhados;
    aqui se cobra que a perna **desta** superfície seja uma delas, e não YAML
    copiado. Um repositório com duas superfícies é cobrado nas duas.
    """
    ci = anatomy.shared_ci
    if ci is None:
        return []
    return [
        AnatomyItem(
            id=f"{surface.name}-ci-referencia-perna-compartilhada",
            scope=stack(surface.name),
            applies=lambda repo, s=surface, c=ci: (
                s.name in repo.surfaces and c.caller in repo.files
            ),
            satisfied=lambda repo, s=surface, c=ci: s.ci_workflow in (repo.content(c.caller) or ""),
            motivo=lambda repo, s=surface, c=ci: (
                f"{repo.name} tem superfície {s.name} e {c.caller} não referencia "
                f"{s.ci_workflow}: a perna daquela superfície é YAML próprio, que já divergiu "
                "uma vez na frota inteira"
            ),
        )
    ]
