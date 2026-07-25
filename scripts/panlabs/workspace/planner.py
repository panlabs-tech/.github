"""Onde toda decisão sobre o espaço de trabalho mora. Puro, testado.

Cinco eixos, e cada um tem uma decisão que não é óbvia:

- **aditivo**: o alvo é a org viva, nunca um manifesto. É essa escolha que faz repo
  novo entrar sozinho e impede a regra de divergir da realidade. E ela é só da org:
  repositório pessoal apagado nunca é re-clonado, senão a regra aditiva desfaria a
  faxina em toda rodada.
- **remotes**: a reescrita é do repositório, e worktree compartilha o remote do pai.
  Uma reescrita por worktree seria a mesma reescrita repetida sobre o mesmo alvo.
- **preflight**: o alvo é derivado da máquina, e vem **antes** de qualquer descarte.
  É o único sequenciamento obrigatório entre as duas metades desta issue.
- **layout**: mover quebra o vínculo do worktree com o pai, porque o ponteiro de
  volta é caminho absoluto dos dois lados. Reparar é item de plano, não detalhe.
- **subtrativo**: elegibilidade é sugestão, e todo descarte nasce **retido**. Só um
  alvo nomeado pelo operador vira aplicável, um a um.

Duas coisas que este planner deliberadamente **não** faz:

**Não olha o relógio.** Não é promessa: `WorkDir` não tem campo de data, então um
critério com eixo de recência não teria de onde tirá-la. Um projeto parado há um
ano não é um projeto morto.

**Não decide por identificador de commit.** Sob squash-merge os identificadores
divergem enquanto o conteúdo é idêntico, e foi assim que uma varredura anterior
gerou alarme falso de 30 commits em 22 branches supostamente ausentes de todo
remote. Só `content_on_remote` decide; `commit_on_remote` existe para ser medido e
não usado.
"""

from __future__ import annotations

from collections.abc import Iterable

from panlabs.plan import Plan, PlanItem
from panlabs.workspace.config import Desired
from panlabs.workspace.model import EMPTY, REPO, WORKTREE, Observed, WorkDir

__all__ = [
    "CLONE_REPO",
    "COMMIT_LOCAL",
    "DISCARD_DIR",
    "DISCARD_WORKTREE",
    "DROP_STASH",
    "MOVE_REPO",
    "MOVE_WORKTREE",
    "PRESERVE_STASH",
    "PUSH_BRANCH",
    "REPAIR_WORKTREE",
    "REWRITE_REMOTE",
    "plan",
]

CLONE_REPO = "clone-repo"
REWRITE_REMOTE = "rewrite-remote"
COMMIT_LOCAL = "commit-local"
PUSH_BRANCH = "push-branch"
PRESERVE_STASH = "preserve-stash"
DROP_STASH = "drop-stash"
MOVE_REPO = "move-repo"
MOVE_WORKTREE = "move-worktree"
REPAIR_WORKTREE = "repair-worktree-link"
DISCARD_DIR = "discard-dir"
DISCARD_WORKTREE = "discard-worktree"

DISCARD_HOLD = (
    "elegibilidade é sugestão, e apagar é irreversível: nomeie este alvo em --discard "
    "para autorizá-lo, um a um"
)

PRESERVE_PREFIX = "preservado"
"""O prefixo das branches que o preflight cria para trabalho sem branch própria."""

COMMIT_MESSAGE = "chore: preserva o trabalho que só existia neste disco"
"""A mensagem do commit do preflight, decidida aqui para o applier não decidir nada."""


def plan(observed: Observed, desired: Desired, *, approved: Iterable[str] = ()) -> Plan:
    """De estado observado e dado desejado para plano. Sem efeito, sem exceção.

    A ordem das seções é a ordem de leitura **e** a ordem de aplicação, e é
    deliberada. O remote é reescrito antes de qualquer push, para que o trabalho
    preservado não viaje por um redirect. O preflight vem antes do layout e do
    descarte, porque preservar precede mexer. O descarte é sempre o último.
    """
    at_risk = {entry.path for entry in observed.dirs if _at_risk(entry, observed)}
    doomed = {entry.path for entry in observed.dirs if _spent_worktree(entry)}
    final = _final_paths(observed, desired, doomed)
    okay = set(approved)

    items: list[PlanItem] = []
    items.extend(_rewrite_items(observed, desired))
    items.extend(_clone_items(observed, desired))
    items.extend(_preflight_items(observed, at_risk))
    items.extend(_layout_items(observed, desired, final, doomed))
    items.extend(_discard_items(observed, final, doomed, okay))
    return Plan(items=tuple(items))


# --- quem é da org, e quem só parece ser --------------------------------------


def _is_org_clone(entry: WorkDir, observed: Observed, desired: Desired) -> bool:
    """Este diretório é o clone local de um repositório da org?

    Quem responde é o **remote**, não o nome do diretório: `~/workspaces/travelmanager`
    é o clone de um repo da org mesmo com o diretório plano e o remote apontando
    para a conta antiga. A conta antiga conta como da org porque o repo migrou, e é
    justamente esse remote que a reescrita conserta.
    """
    if entry.kind != REPO or not entry.remote:
        return False
    if entry.repo_name not in observed.org_repos:
        return False
    return entry.owner == observed.org or entry.owner in (desired.migrated_from or ())


def _at_risk(entry: WorkDir, observed: Observed) -> bool:
    """Este repositório é candidato a sair da máquina algum dia?

    Deliberadamente mais largo que `_is_org_clone`: aqui basta o **nome** estar na
    org para o diretório nunca correr risco. Um homônimo de outro dono não é da org
    e ainda assim fica de fora, porque este predicado só serve para vetar descarte
    e para trazer stash para o preflight, e nas duas o erro seguro é para o lado de
    preservar. Quando `migrated_from` ainda não foi decidido, é este predicado que
    impede um repo da org de aparecer como descartável só porque o remote é antigo.
    """
    return entry.kind == REPO and bool(entry.remote) and entry.repo_name not in observed.org_repos


def _spent_worktree(entry: WorkDir) -> bool:
    """Um worktree que não carrega mais nada que só exista aqui.

    A comparação é de **conteúdo**. Um worktree cujo identificador divergiu sob
    squash-merge continua gasto, porque o que ele carrega já está no remote.
    """
    return entry.kind == WORKTREE and not entry.only_local


# --- o layout final de cada diretório, antes de qualquer item -----------------


def _final_paths(observed: Observed, desired: Desired, doomed: set[str]) -> dict[str, str]:
    """Onde cada diretório termina, calculado uma vez e usado por todo o resto.

    Sem isto, cada seção recalcularia o endereço final e elas divergiriam: um
    worktree aninhado num pai que anda **anda junto**, sem item de movimentação
    próprio, e ainda assim precisa de reparo porque o caminho absoluto mudou.
    """
    final = {entry.path: entry.path for entry in observed.dirs}

    for entry in observed.dirs:
        if _is_org_clone(entry, observed, desired) and observed.root and observed.org:
            final[entry.path] = f"{observed.root}/{observed.org}/{entry.repo_name}"

    for entry in observed.dirs:
        if entry.kind != WORKTREE:
            continue
        carried = _carried(entry.path, entry.parent, final.get(entry.parent, entry.parent))
        if entry.path in doomed or desired.worktrees is None:
            final[entry.path] = carried
            continue
        parent_final = final.get(entry.parent, entry.parent)
        final[entry.path] = f"{parent_final}/{desired.worktrees}/{entry.name}"

    return final


def _carried(path: str, parent: str, parent_final: str) -> str:
    """O endereço de um worktree depois de o pai andar, sem movê-lo por conta própria."""
    if parent and path.startswith(f"{parent}/"):
        return parent_final + path[len(parent) :]
    return path


# --- a metade aditiva ---------------------------------------------------------


def _rewrite_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    """O remote precisa dizer a verdade, e antes de qualquer coisa empurrar por ele.

    Só o repositório entra: worktree compartilha o `.git` do pai, e portanto o
    remote. Uma reescrita por worktree seria a mesma reescrita, repetida.
    """
    riders: dict[str, int] = {}
    for entry in observed.dirs:
        if entry.kind == WORKTREE and entry.parent:
            riders[entry.parent] = riders.get(entry.parent, 0) + 1

    items: list[PlanItem] = []
    for entry in observed.dirs:
        if not _is_org_clone(entry, observed, desired):
            continue
        canonical = desired.url_for(observed.org, entry.repo_name)
        if not canonical or entry.remote == canonical:
            continue
        hanging = riders.get(entry.path, 0)
        items.append(
            PlanItem(
                action=REWRITE_REMOTE,
                target=entry.path,
                reason=(
                    f"o remote aponta para {entry.owner} e só funciona por redirect, "
                    f"que mente para quem lê o remote como dado; "
                    f"{hanging} worktree(s) compartilham este mesmo remote"
                ),
                payload={"url": canonical, "was": entry.remote},
            )
        )
    return items


def _clone_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    """Todo repositório da org tem clone. Uniforme, sem exceção.

    Nenhuma afirmação equivalente sobre o que não é da org: um repositório pessoal
    apagado de propósito nunca é re-clonado, senão a regra aditiva desfaria a faxina.

    O repo meta da org tem nome começando por ponto, e aqui ele não é caso especial
    nenhum: o alvo é a listagem da org, e ela não filtra oculto. É o glob de disco
    que perderia esse repo, e por isso o alvo não é o disco.
    """
    if desired.remote is None or not observed.root or not observed.org:
        return []

    present = {
        entry.repo_name for entry in observed.dirs if _is_org_clone(entry, observed, desired)
    }
    return [
        PlanItem(
            action=CLONE_REPO,
            target=f"{observed.root}/{observed.org}/{name}",
            reason=(
                f"`{name}` está na org viva e não tem clone nesta máquina; "
                "todo repositório da org tem clone, sem exceção"
            ),
            payload={"url": desired.url_for(observed.org, name), "name": name},
        )
        for name in observed.org_repos
        if name not in present
    ]


# --- o preflight: nada que só existe local se perde ---------------------------


def _preflight_items(observed: Observed, at_risk: set[str]) -> list[PlanItem]:
    """Commita e pusha o que só existe local. Sem tarball, sem arquivo fora do git.

    O alvo é derivado da máquina, e não de uma lista: a lista original nomeava três
    repositórios, e quatro dias depois um quarto, este da própria org, apareceu com
    dezenas de arquivos sujos. A decisão continua válida; a lista, não.

    Um refspec é emitido uma vez por repositório, e não uma por árvore de trabalho:
    a branch que um worktree carrega é branch do pai, e empurrá-la duas vezes seria
    o mesmo push escrito duas vezes no plano.
    """
    items: list[PlanItem] = []
    pushed: set[tuple[str, str]] = set()

    for entry in observed.dirs:
        if not entry.is_git:
            continue
        store = entry.parent or entry.path
        items.extend(_commit_items(entry))
        for refspec, why in _refspecs(entry):
            if (store, refspec) in pushed:
                continue
            pushed.add((store, refspec))
            items.append(
                PlanItem(
                    action=PUSH_BRANCH,
                    target=entry.path,
                    reason=why,
                    payload={"refspec": refspec},
                )
            )
        items.extend(_stash_items(entry, at_risk))
    return items


def _commit_items(entry: WorkDir) -> list[PlanItem]:
    if not entry.dirty:
        return []
    return [
        PlanItem(
            action=COMMIT_LOCAL,
            target=entry.path,
            reason=(
                f"{len(entry.dirty)} arquivo(s) só existem neste disco; "
                "o status do git colapsa diretório não rastreado e subcontaria isto"
            ),
            payload={"files": list(entry.dirty), "message": COMMIT_MESSAGE},
        )
    ]


def _refspecs(entry: WorkDir) -> list[tuple[str, str]]:
    """O que precisa subir, e por quê. Conteúdo decide; identificador nunca.

    Uma branch cujo conteúdo já está no remote não aparece aqui nem quando o
    identificador dela divergiu, que é exatamente o estado que o squash-merge
    produz e o que gerou o alarme falso já sofrido.
    """
    out = [
        (
            f"{branch.name}:refs/heads/{branch.name}",
            f"o conteúdo de `{branch.name}` não está em remote nenhum",
        )
        for branch in entry.unpushed
    ]
    if not entry.dirty:
        return out

    if entry.head:
        landing = f"{entry.head}:refs/heads/{entry.head}"
        why = f"`{entry.head}` recebe o commit do preflight e precisa subir com ele"
    else:
        landing = f"HEAD:refs/heads/{PRESERVE_PREFIX}/{entry.name}"
        why = "HEAD destacada: o commit do preflight sobe numa branch nomeada pelo diretório"
    if landing not in {refspec for refspec, _ in out}:
        out.append((landing, why))
    return out


def _stash_items(entry: WorkDir, at_risk: set[str]) -> list[PlanItem]:
    """Stash de repositório que fica na máquina não está em risco, e não entra aqui.

    Os órfãos, de branch que não existe mais nem local nem no remote, são
    descartados: eles não se aplicam a nada. Os vivos sobem como branch, porque a
    regra única é commitar e empurrar o que só existe local, e stash é exatamente
    isso.

    Os descartes saem em ordem decrescente de índice porque descartar um stash
    desloca os de baixo. Isso é decisão de plano, e não do applier: quem percorre a
    tabela de despacho não pode precisar saber disso.
    """
    if entry.path not in at_risk or not entry.stashes:
        return []

    items = [
        PlanItem(
            action=PRESERVE_STASH,
            target=entry.path,
            reason=(
                f"`{stash.ref}` só existe neste disco e a branch `{stash.branch}` ainda "
                "existe; o repositório é candidato a sair da máquina"
            ),
            payload={
                "sha": stash.sha,
                "ref": stash.ref,
                "branch": f"{PRESERVE_PREFIX}/{_slot(stash.ref)}-{entry.name}",
            },
        )
        for stash in entry.stashes
        if stash.branch_alive
    ]
    items.extend(
        PlanItem(
            action=DROP_STASH,
            target=entry.path,
            reason=(
                f"`{stash.ref}` nasceu em `{stash.branch}`, que não existe mais nem local "
                "nem em remote nenhum: não há a que aplicá-lo"
            ),
            payload={"ref": stash.ref, "sha": stash.sha},
        )
        for stash in reversed([stash for stash in entry.stashes if not stash.branch_alive])
    )
    return items


def _slot(ref: str) -> str:
    """`stash@{2}` vira `2`, que é o que dá nome único à branch de preservação."""
    return ref.rsplit("{", 1)[-1].rstrip("}") or ref


# --- o layout: org sob a org, worktree dentro do pai --------------------------


def _layout_items(
    observed: Observed, desired: Desired, final: dict[str, str], doomed: set[str]
) -> list[PlanItem]:
    """Primeiro os pais, depois os worktrees, e só então os reparos.

    A ordem não é estética: reparar um vínculo antes de o pai chegar ao endereço
    final o gravaria apontando para onde o pai não está mais.
    """
    moves = [
        PlanItem(
            action=MOVE_REPO,
            target=entry.path,
            reason=(
                "repositório da org fora do diretório que espelha a org; "
                "é o caminho que torna visível a fronteira entre org e pessoal"
            ),
            payload={"to": final[entry.path]},
        )
        for entry in observed.dirs
        if entry.kind == REPO and final[entry.path] != entry.path
    ]

    moves.extend(
        PlanItem(
            action=MOVE_WORKTREE,
            target=entry.path,
            reason=(
                f"worktree solto ao lado do pai `{_name_of(entry.parent)}`; "
                "aninhá-lo torna visível na árvore a relação que hoje só existe no git"
            ),
            payload={"to": final[entry.path], "parent": final.get(entry.parent, entry.parent)},
        )
        for entry in observed.dirs
        if entry.kind == WORKTREE
        and entry.path not in doomed
        and final[entry.path]
        != _carried(entry.path, entry.parent, final.get(entry.parent, entry.parent))
    )

    moves.extend(
        PlanItem(
            action=REPAIR_WORKTREE,
            target=final[entry.path],
            reason=(
                "o ponteiro de volta ao pai é caminho absoluto dos dois lados, e mudar "
                "de endereço qualquer um dos dois o quebra em silêncio"
            ),
            payload={
                "parent": final.get(entry.parent, entry.parent),
                "worktree": final[entry.path],
            },
        )
        for entry in observed.dirs
        if entry.kind == WORKTREE and _link_broken(entry, final)
    )
    return moves


def _link_broken(entry: WorkDir, final: dict[str, str]) -> bool:
    """O vínculo quebra quando **qualquer um dos dois lados** muda de endereço.

    O worktree solto de um pai que anda é o caso que só se enxerga olhando o pai:
    ele mesmo fica exatamente onde estava, e ainda assim para de funcionar, porque
    o `.git` dele nomeia um `.git` de pai que não existe mais naquele caminho.
    Um worktree proposto para descarte também precisa do reparo: sem ele o próprio
    `git worktree remove` não acha mais o que remover.
    """
    parent = entry.parent
    return final[entry.path] != entry.path or final.get(parent, parent) != parent


def _name_of(path: str) -> str:
    return path.rsplit("/", 1)[-1]


# --- a metade subtrativa: sugestão, nunca decisão -----------------------------


def _discard_items(
    observed: Observed, final: dict[str, str], doomed: set[str], approved: set[str]
) -> list[PlanItem]:
    """O critério, e a razão de ele nunca virar ato sozinho.

    Elegibilidade é sugestão: todo item nasce retido, e só um alvo que o operador
    nomeou vira aplicável. A máquina não toma decisão irreversível pelo operador.
    """
    items: list[PlanItem] = []
    for entry in observed.dirs:
        reason = _why_disposable(entry, observed)
        if reason is None and entry.path not in doomed:
            continue
        action = DISCARD_WORKTREE if entry.kind == WORKTREE else DISCARD_DIR
        target = final[entry.path]
        items.append(
            PlanItem(
                action=action,
                target=target,
                reason=reason or _WORKTREE_REASON,
                payload={"path": target, "parent": final.get(entry.parent, entry.parent)},
                hold="" if target in approved else DISCARD_HOLD,
            )
        )
    return items


_WORKTREE_REASON = (
    "todo o conteúdo deste worktree já está em algum remote; a comparação é de "
    "conteúdo, e não de identificador de commit, que o squash-merge faz divergir"
)


def _why_disposable(entry: WorkDir, observed: Observed) -> str | None:
    """O motivo de um diretório ser elegível, ou `None` se ele não é.

    Três cláusulas, e nenhuma delas olha o relógio: não pertence à org, tem remote,
    e está pushado. Diretório vazio é sempre elegível, porque não há o que preservar.
    """
    if entry.kind == EMPTY:
        return "diretório vazio: não há nada aqui para preservar"
    if entry.kind != REPO:
        return None
    if not _at_risk(entry, observed):
        return None
    if entry.only_local:
        return None
    return (
        "não é da org, tem remote e está pushado: tudo aqui existe em outro lugar, "
        "e o remote é onde ele volta a existir"
    )
