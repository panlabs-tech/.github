"""O planner do espaço de trabalho: de qual estado observado sai qual plano.

Quatro decisões desta issue moram aqui e são o motivo de o planner existir:

1. **O alvo aditivo vem da org viva.** Um repo da org sem clone é planejado para
   clonagem, e o caso que importa é o repo de nome começando por ponto, porque é
   o que um glob ingênuo perde para sempre.
2. **Reescrita de remote é do repositório, não do worktree.** Worktree compartilha
   o remote com o pai, e uma reescrita por worktree seria a mesma reescrita feita
   várias vezes sobre o mesmo alvo.
3. **O critério de descarte não tem eixo de tempo.** Isso não é uma promessa de
   comentário: `WorkDir` não tem campo de data nenhum, então um plano que
   dependesse de recência não teria de onde tirá-la. O teste que prova isso compara
   o motivo de um repo parado há muito tempo com o de qualquer outro.
4. **Conteúdo decide, identificador não.** Sob squash-merge o identificador diverge
   enquanto o conteúdo é idêntico, e foi confundir os dois que gerou o alarme falso
   de 30 commits em 22 branches supostamente ausentes de todo remote.

As fixtures são estado de espaço de trabalho, não a máquina real: os casos que
importam (já reconciliado, worktree aninhado, repo pessoal ausente) são estados
que a máquina viva não está hoje, e são exatamente os que precisam de teste.
"""

from panlabs.plan import Plan, PlanItem
from panlabs.workspace import planner
from panlabs.workspace.config import Desired
from panlabs.workspace.model import (
    EMPTY,
    PLAIN,
    REPO,
    WORKTREE,
    Branch,
    Observed,
    Stash,
    WorkDir,
)

ORG = "panlabs-tech"
ROOT = "/home/op/workspaces"
ORG_DIR = f"{ROOT}/{ORG}"
OLD = "ThiagoPanini"
REMOTE = "https://github.com/{org}/{name}.git"
NEST = ".claude/worktrees"


# --- vocabulário das fixtures -------------------------------------------------


def items_for(the_plan: Plan, action: str) -> list[PlanItem]:
    return [item for item in the_plan if item.action == action]


def targets_for(the_plan: Plan, action: str) -> list[str]:
    return [item.target for item in items_for(the_plan, action)]


def landed(name: str) -> Branch:
    """Uma branch cujo conteúdo e cujo identificador estão os dois no remote."""
    return Branch(name=name, content_on_remote=True, commit_on_remote=True)


def squashed(name: str) -> Branch:
    """O caso do alarme falso: o conteúdo aterrissou, o identificador divergiu."""
    return Branch(name=name, content_on_remote=True, commit_on_remote=False)


def only_here(name: str) -> Branch:
    """Uma branch que só existe neste disco. É a única que o preflight preserva."""
    return Branch(name=name)


def repo(name: str, *, owner: str = OLD, at: str = "", **overrides: object) -> WorkDir:
    fields: dict[str, object] = {
        "path": at or f"{ROOT}/{name}",
        "kind": REPO,
        "remote": f"https://github.com/{owner}/{name}.git" if owner else "",
        "head": "main",
        "branches": (landed("main"),),
    }
    fields.update(overrides)
    return WorkDir(**fields)  # pyright: ignore[reportArgumentType]


def worktree(name: str, parent: WorkDir, *, at: str = "", **overrides: object) -> WorkDir:
    fields: dict[str, object] = {
        "path": at or f"{ROOT}/{name}",
        "kind": WORKTREE,
        "parent": parent.path,
        "remote": parent.remote,
        "head": name,
        "branches": (landed(name),),
    }
    fields.update(overrides)
    return WorkDir(**fields)  # pyright: ignore[reportArgumentType]


def state(*dirs: WorkDir, org_repos: tuple[str, ...] = ()) -> Observed:
    return Observed(org=ORG, root=ROOT, org_repos=org_repos, dirs=dirs)


def wanted(**overrides: object) -> Desired:
    """Uma configuração desejada inteira e decidida, com só o que o teste mexe."""
    base: dict[str, object] = {
        "root": ROOT,
        "remote": REMOTE,
        "migrated_from": (OLD,),
        "worktrees": NEST,
    }
    base.update(overrides)
    return Desired(**base)  # pyright: ignore[reportArgumentType]


# --- a metade aditiva: o alvo vem da org viva ---------------------------------


def test_an_org_repo_with_no_local_clone_is_planned_for_cloning():
    the_plan = planner.plan(state(org_repos=("skills",)), wanted())

    assert targets_for(the_plan, planner.CLONE_REPO) == [f"{ORG_DIR}/skills"]


def test_the_repo_whose_name_starts_with_a_dot_is_cloned_like_any_other():
    """O caso que um glob ingênuo perde: o repo meta da org é diretório oculto."""
    the_plan = planner.plan(state(org_repos=(".github",)), wanted())

    (item,) = items_for(the_plan, planner.CLONE_REPO)
    assert item.target == f"{ORG_DIR}/.github"
    assert item.payload["url"] == f"https://github.com/{ORG}/.github.git"


def test_an_org_repo_already_cloned_anywhere_is_not_cloned_again():
    """Quem responde "este repo já existe aqui" é o remote, não o nome do diretório."""
    the_plan = planner.plan(
        state(repo("travelmanager", owner=ORG), org_repos=("travelmanager",)), wanted()
    )

    assert items_for(the_plan, planner.CLONE_REPO) == []


def test_a_personal_repo_missing_from_disk_is_never_cloned():
    """A regra aditiva é só da org. Sem isso ela desfaria a faxina toda rodada."""
    the_plan = planner.plan(state(org_repos=()), wanted())

    assert items_for(the_plan, planner.CLONE_REPO) == []


def test_a_parent_with_stale_remote_and_worktrees_produces_a_single_rewrite():
    """Worktree compartilha o remote do pai: dez remotes stale, quatro reescritas."""
    parent = repo("travelmanager", at=f"{ORG_DIR}/travelmanager")
    the_plan = planner.plan(
        state(
            parent,
            worktree("wt-212", parent, at=f"{ORG_DIR}/travelmanager/{NEST}/wt-212"),
            worktree("wt-213", parent, at=f"{ORG_DIR}/travelmanager/{NEST}/wt-213"),
            org_repos=("travelmanager",),
        ),
        wanted(),
    )

    assert targets_for(the_plan, planner.REWRITE_REMOTE) == [parent.path]


def test_the_rewrite_says_how_many_worktrees_ride_on_the_same_remote():
    parent = repo("travelmanager", at=f"{ORG_DIR}/travelmanager")
    the_plan = planner.plan(
        state(
            parent,
            worktree("wt-212", parent, at=f"{ORG_DIR}/travelmanager/{NEST}/wt-212"),
            org_repos=("travelmanager",),
        ),
        wanted(),
    )

    (item,) = items_for(the_plan, planner.REWRITE_REMOTE)
    assert "1 worktree" in item.reason


def test_a_personal_repo_keeps_its_remote_untouched():
    """O invariante é só da org, e invadir o que não é dela seria outra regra."""
    the_plan = planner.plan(state(repo("b3stocks"), org_repos=("travelmanager",)), wanted())

    assert items_for(the_plan, planner.REWRITE_REMOTE) == []


def test_a_personal_repo_that_shares_a_name_with_an_org_repo_is_still_personal():
    """Só o dono decide, e o dono de um repo pessoal não está na lista de migração."""
    the_plan = planner.plan(
        state(repo("panlabs", owner="outra-pessoa"), org_repos=("panlabs",)), wanted()
    )

    assert items_for(the_plan, planner.REWRITE_REMOTE) == []
    assert targets_for(the_plan, planner.CLONE_REPO) == [f"{ORG_DIR}/panlabs"]


def test_an_org_remote_already_canonical_is_not_rewritten():
    the_plan = planner.plan(
        state(repo("panlabs", owner=ORG, at=f"{ORG_DIR}/panlabs"), org_repos=("panlabs",)), wanted()
    )

    assert items_for(the_plan, planner.REWRITE_REMOTE) == []


def test_an_already_reconciled_workspace_produces_an_empty_plan():
    the_plan = planner.plan(
        state(
            repo("panlabs", owner=ORG, at=f"{ORG_DIR}/panlabs"),
            repo("traveltogether", owner=""),
            org_repos=("panlabs",),
        ),
        wanted(),
    )

    assert len(the_plan) == 0


# --- o layout: org sob o diretório da org, worktree dentro do pai -------------


def test_an_org_repo_sitting_flat_is_planned_to_move_under_the_org_dir():
    the_plan = planner.plan(
        state(repo("travelmanager", owner=ORG), org_repos=("travelmanager",)), wanted()
    )

    (item,) = items_for(the_plan, planner.MOVE_REPO)
    assert item.target == f"{ROOT}/travelmanager"
    assert item.payload["to"] == f"{ORG_DIR}/travelmanager"


def test_a_personal_repo_stays_flat_because_the_layout_rule_is_the_org_s():
    the_plan = planner.plan(state(repo("b3stocks"), org_repos=()), wanted())

    assert items_for(the_plan, planner.MOVE_REPO) == []


def test_moving_a_worktree_plans_repairing_the_link_with_the_parent():
    """O ponteiro de volta é caminho absoluto dos dois lados, e mover o quebra."""
    parent = repo("travelmanager", owner=ORG, at=f"{ORG_DIR}/travelmanager")
    loose = worktree("wt-212", parent, branches=(only_here("feat/212"),))

    the_plan = planner.plan(state(parent, loose, org_repos=("travelmanager",)), wanted())

    (move,) = items_for(the_plan, planner.MOVE_WORKTREE)
    (repair,) = items_for(the_plan, planner.REPAIR_WORKTREE)
    assert move.payload["to"] == f"{parent.path}/{NEST}/wt-212"
    assert repair.target == f"{parent.path}/{NEST}/wt-212"
    assert repair.payload["parent"] == parent.path


def test_a_worktree_already_nested_in_its_parent_is_not_moved():
    parent = repo("travelmanager", owner=ORG, at=f"{ORG_DIR}/travelmanager")
    nested = worktree(
        "wt-212", parent, at=f"{parent.path}/{NEST}/wt-212", branches=(only_here("feat/212"),)
    )

    the_plan = planner.plan(state(parent, nested, org_repos=("travelmanager",)), wanted())

    assert items_for(the_plan, planner.MOVE_WORKTREE) == []
    assert items_for(the_plan, planner.REPAIR_WORKTREE) == []


def test_a_loose_worktree_whose_parent_moves_is_repaired_even_standing_still():
    """O caso que só se enxerga olhando o pai: o worktree fica onde estava e quebra.

    Ele não anda, então nenhuma comparação sobre o próprio endereço o pegaria. O
    `.git` dele nomeia um `.git` de pai que deixou de existir naquele caminho, e o
    worktree para de funcionar em silêncio, que é exatamente o desfecho que a spec
    nomeia como inaceitável.
    """
    parent = repo("travelmanager", owner=ORG)
    loose = worktree("wt-212", parent)

    the_plan = planner.plan(state(parent, loose, org_repos=("travelmanager",)), wanted())

    (repair,) = items_for(the_plan, planner.REPAIR_WORKTREE)
    assert repair.target == loose.path
    assert repair.payload["parent"] == f"{ORG_DIR}/travelmanager"


def test_a_worktree_proposed_for_discard_is_still_repaired_when_the_parent_moves():
    """Sem o reparo o próprio `git worktree remove` não acha mais o que remover."""
    parent = repo("travelmanager", owner=ORG)
    done = worktree("wt-212", parent, at=f"{parent.path}/{NEST}/wt-212")

    the_plan = planner.plan(state(parent, done, org_repos=("travelmanager",)), wanted())

    order = [item.action for item in the_plan]
    assert order.index(planner.REPAIR_WORKTREE) < order.index(planner.DISCARD_WORKTREE)


def test_a_nested_worktree_whose_parent_moves_is_repaired_at_the_new_address():
    """O vínculo quebra dos dois lados quando o pai anda, mesmo o worktree parado."""
    parent = repo("travelmanager", owner=ORG)
    nested = worktree(
        "wt-212", parent, at=f"{parent.path}/{NEST}/wt-212", branches=(only_here("feat/212"),)
    )

    the_plan = planner.plan(state(parent, nested, org_repos=("travelmanager",)), wanted())

    (repair,) = items_for(the_plan, planner.REPAIR_WORKTREE)
    assert repair.payload["parent"] == f"{ORG_DIR}/travelmanager"
    assert repair.target == f"{ORG_DIR}/travelmanager/{NEST}/wt-212"


def test_the_move_of_a_parent_comes_before_the_repair_of_its_worktrees():
    """Reparar um vínculo antes de o pai chegar no lugar final seria repará-lo errado."""
    parent = repo("travelmanager", owner=ORG)
    loose = worktree("wt-212", parent, branches=(only_here("feat/212"),))

    the_plan = planner.plan(state(parent, loose, org_repos=("travelmanager",)), wanted())

    order = [item.action for item in the_plan]
    assert order.index(planner.MOVE_REPO) < order.index(planner.MOVE_WORKTREE)
    assert order.index(planner.MOVE_WORKTREE) < order.index(planner.REPAIR_WORKTREE)


# --- o critério de descarte: sem eixo de tempo, e sempre sugestão -------------


def test_an_org_repo_is_never_eligible_for_discard_even_when_fully_pushed():
    the_plan = planner.plan(
        state(repo("panlabs", owner=ORG, at=f"{ORG_DIR}/panlabs"), org_repos=("panlabs",)), wanted()
    )

    assert items_for(the_plan, planner.DISCARD_DIR) == []


def test_a_personal_repo_without_a_remote_is_never_eligible():
    """Sem remote, apagar não é faxina: é perda. Nada o substitui."""
    the_plan = planner.plan(state(repo("traveltogether", owner="")), wanted())

    assert items_for(the_plan, planner.DISCARD_DIR) == []


def test_a_personal_repo_with_unpushed_content_is_never_eligible():
    the_plan = planner.plan(
        state(repo("campfire", branches=(landed("main"), only_here("mvp/lofi")))), wanted()
    )

    assert items_for(the_plan, planner.DISCARD_DIR) == []


def test_a_personal_repo_with_a_dirty_working_tree_is_never_eligible():
    the_plan = planner.plan(state(repo("campfire", dirty=("notes.md",))), wanted())

    assert items_for(the_plan, planner.DISCARD_DIR) == []


def test_a_personal_repo_with_a_remote_and_fully_pushed_is_eligible():
    the_plan = planner.plan(state(repo("b3stocks")), wanted())

    assert targets_for(the_plan, planner.DISCARD_DIR) == [f"{ROOT}/b3stocks"]


def test_an_empty_dir_is_always_eligible():
    the_plan = planner.plan(state(WorkDir(path=f"{ROOT}/luc-wt", kind=EMPTY)), wanted())

    assert targets_for(the_plan, planner.DISCARD_DIR) == [f"{ROOT}/luc-wt"]


def test_a_dir_with_content_and_no_git_is_never_eligible():
    """Não tem remote, logo não passa no critério. O mesmo teste dos repos sem remote."""
    the_plan = planner.plan(state(WorkDir(path=f"{ROOT}/hashnode-backup", kind=PLAIN)), wanted())

    assert items_for(the_plan, planner.DISCARD_DIR) == []


def test_a_long_idle_pushed_repo_is_eligible_for_the_very_same_reason():
    """Não há eixo de tempo escondido, e não teria de onde vir: o modelo não tem data.

    O teste compara os dois motivos em vez de checar uma palavra: se algum dia
    entrasse recência no critério, é o motivo que denunciaria primeiro.
    """
    the_plan = planner.plan(state(repo("callisto"), repo("b3stocks")), wanted())

    idle, fresh = items_for(the_plan, planner.DISCARD_DIR)
    assert idle.reason == fresh.reason


def test_no_discard_is_applicable_without_explicit_per_target_approval():
    """Elegibilidade é sugestão. A decisão de apagar continua humana, alvo por alvo."""
    the_plan = planner.plan(
        state(repo("b3stocks"), WorkDir(path=f"{ROOT}/x", kind=EMPTY)), wanted()
    )

    assert len(items_for(the_plan, planner.DISCARD_DIR)) == 2
    assert the_plan.applicable == ()


def test_only_the_approved_target_becomes_applicable():
    the_plan = planner.plan(
        state(repo("b3stocks"), repo("callisto")),
        wanted(),
        approved=(f"{ROOT}/b3stocks",),
    )

    assert [item.target for item in the_plan.applicable] == [f"{ROOT}/b3stocks"]
    assert [item.target for item in the_plan.held] == [f"{ROOT}/callisto"]


# --- o preflight: nada que só existe local se perde ---------------------------


def test_a_dirty_repo_that_no_written_list_named_shows_up_in_the_plan():
    """O alvo é derivado da máquina: a lista original nomeava três repos, e um
    quarto, este da própria org, apareceu sujo quatro dias depois."""
    the_plan = planner.plan(
        state(
            repo(".github", owner=ORG, at=f"{ORG_DIR}/.github", dirty=("docs/novo.md",)),
            org_repos=(".github",),
        ),
        wanted(),
    )

    assert targets_for(the_plan, planner.COMMIT_LOCAL) == [f"{ORG_DIR}/.github"]


def test_the_preservation_item_carries_every_file_the_collapsed_dir_would_hide():
    """O default do git colapsa diretório não rastreado num item só e subconta."""
    dirty = ("rascunho/a.md", "rascunho/b.md", "rascunho/c.md")
    the_plan = planner.plan(state(repo("campfire", dirty=dirty)), wanted())

    (item,) = items_for(the_plan, planner.COMMIT_LOCAL)
    assert item.payload["files"] == list(dirty)
    assert "3 arquivo" in item.reason


def test_a_branch_landed_by_squash_merge_is_not_reported_as_absent_from_the_remote():
    """O alarme falso já sofrido: 30 commits em 22 branches, todas já no remote."""
    the_plan = planner.plan(
        state(
            repo(
                "travelmanager",
                owner=ORG,
                at=f"{ORG_DIR}/travelmanager",
                branches=(
                    landed("main"),
                    squashed("feat/212-login-otp-timer-copy"),
                ),
            ),
            org_repos=("travelmanager",),
        ),
        wanted(),
    )

    assert items_for(the_plan, planner.PUSH_BRANCH) == []


def test_a_branch_whose_content_is_nowhere_is_planned_for_pushing():
    the_plan = planner.plan(
        state(repo("campfire", branches=(landed("main"), only_here("mvp/lofi")))), wanted()
    )

    (item,) = items_for(the_plan, planner.PUSH_BRANCH)
    assert item.payload["refspec"] == "mvp/lofi:refs/heads/mvp/lofi"


def test_a_dirty_repo_pushes_the_branch_it_just_committed_onto():
    """Commitar sem empurrar deixaria o trabalho exatamente onde ele já estava."""
    the_plan = planner.plan(state(repo("campfire", dirty=("notes.md",))), wanted())

    assert targets_for(the_plan, planner.PUSH_BRANCH) == [f"{ROOT}/campfire"]


def test_a_dirty_detached_head_is_preserved_on_a_branch_named_for_the_dir():
    """HEAD destacada dá para commitar e não dá para dizer em que branch."""
    the_plan = planner.plan(
        state(repo("campfire", head="", dirty=("notes.md",), branches=())), wanted()
    )

    (item,) = items_for(the_plan, planner.PUSH_BRANCH)
    assert item.payload["refspec"] == "HEAD:refs/heads/preservado/campfire"


def test_the_commit_of_a_dir_comes_before_the_push_of_the_same_dir():
    the_plan = planner.plan(state(repo("campfire", dirty=("notes.md",))), wanted())

    order = [item.action for item in the_plan]
    assert order.index(planner.COMMIT_LOCAL) < order.index(planner.PUSH_BRANCH)


def test_the_preflight_precedes_every_discard_in_plan_order():
    """O único sequenciamento obrigatório entre as duas metades desta issue."""
    the_plan = planner.plan(
        state(repo("campfire", dirty=("notes.md",)), repo("b3stocks")), wanted()
    )

    order = [item.action for item in the_plan]
    assert max(order.index(planner.COMMIT_LOCAL), order.index(planner.PUSH_BRANCH)) < order.index(
        planner.DISCARD_DIR
    )


# --- stashes: só os do que vai embora, e só os órfãos são descartados ---------


def test_an_orphan_stash_of_a_repo_at_risk_is_planned_for_discard():
    orphan = Stash(ref="stash@{0}", sha="abc123", branch="visual-reset", branch_alive=False)
    the_plan = planner.plan(state(repo("campfire", stashes=(orphan,))), wanted())

    (item,) = items_for(the_plan, planner.DROP_STASH)
    assert item.payload["ref"] == "stash@{0}"


def test_a_stash_of_a_repo_that_stays_never_enters_the_preflight():
    """Stash de repositório que fica na máquina não está em risco."""
    orphan = Stash(ref="stash@{0}", sha="abc123", branch="sumida", branch_alive=False)
    the_plan = planner.plan(
        state(
            repo("travelmanager", owner=ORG, at=f"{ORG_DIR}/travelmanager", stashes=(orphan,)),
            org_repos=("travelmanager",),
        ),
        wanted(),
    )

    assert items_for(the_plan, planner.DROP_STASH) == []
    assert items_for(the_plan, planner.PRESERVE_STASH) == []


def test_a_living_stash_of_a_repo_at_risk_is_preserved_instead_of_dropped():
    alive = Stash(ref="stash@{0}", sha="abc123", branch="mvp/lofi", branch_alive=True)
    the_plan = planner.plan(state(repo("campfire", stashes=(alive,))), wanted())

    (item,) = items_for(the_plan, planner.PRESERVE_STASH)
    assert item.payload["sha"] == "abc123"
    assert items_for(the_plan, planner.DROP_STASH) == []


def test_stashes_are_dropped_from_the_highest_index_down():
    """Descartar por índice desloca os de baixo, e a ordem é decisão do planner."""
    stashes = tuple(
        Stash(ref=f"stash@{{{n}}}", sha=f"sha{n}", branch="sumida", branch_alive=False)
        for n in range(3)
    )
    the_plan = planner.plan(state(repo("campfire", stashes=stashes)), wanted())

    assert [item.payload["ref"] for item in items_for(the_plan, planner.DROP_STASH)] == [
        "stash@{2}",
        "stash@{1}",
        "stash@{0}",
    ]


# --- worktree: conteúdo decide, identificador nunca ---------------------------


def test_a_worktree_whose_content_is_on_the_remote_is_proposed_for_discard():
    parent = repo("travelmanager", owner=ORG, at=f"{ORG_DIR}/travelmanager")
    done = worktree("wt-212", parent, at=f"{parent.path}/{NEST}/wt-212")

    the_plan = planner.plan(state(parent, done, org_repos=("travelmanager",)), wanted())

    assert targets_for(the_plan, planner.DISCARD_WORKTREE) == [done.path]


def test_a_divergent_commit_with_identical_content_proposes_no_preservation():
    """Sob squash-merge o identificador diverge e o conteúdo não. Só o conteúdo decide:
    o descarte é proposto pelo conteúdo, e a divergência de identificador sozinha
    não produz item nenhum de preservação."""
    parent = repo("travelmanager", owner=ORG, at=f"{ORG_DIR}/travelmanager")
    done = worktree(
        "wt-212",
        parent,
        at=f"{parent.path}/{NEST}/wt-212",
        branches=(squashed("feat/212-login-otp-timer-copy"),),
    )

    the_plan = planner.plan(state(parent, done, org_repos=("travelmanager",)), wanted())

    assert items_for(the_plan, planner.PUSH_BRANCH) == []
    (item,) = items_for(the_plan, planner.DISCARD_WORKTREE)
    assert "conteúdo" in item.reason


def test_a_worktree_carrying_work_is_never_proposed_for_discard():
    parent = repo("travelmanager", owner=ORG, at=f"{ORG_DIR}/travelmanager")
    live = worktree(
        "wt-216",
        parent,
        at=f"{parent.path}/{NEST}/wt-216",
        branches=(only_here("feat/216-home-foco-central"),),
    )

    the_plan = planner.plan(state(parent, live, org_repos=("travelmanager",)), wanted())

    assert items_for(the_plan, planner.DISCARD_WORKTREE) == []


def test_a_worktree_proposed_for_discard_is_not_moved_into_the_parent():
    """A regra de layout é sobre worktree que carrega trabalho; o que já aterrissou
    por inteiro é descartável, e mover antes de descartar seria trabalho jogado fora."""
    parent = repo("travelmanager", owner=ORG, at=f"{ORG_DIR}/travelmanager")
    done = worktree("wt-212", parent)

    the_plan = planner.plan(state(parent, done, org_repos=("travelmanager",)), wanted())

    assert items_for(the_plan, planner.MOVE_WORKTREE) == []
    assert targets_for(the_plan, planner.DISCARD_WORKTREE) == [done.path]


def test_a_worktree_is_never_a_plain_discard_because_removing_it_is_a_git_act():
    parent = repo("travelmanager", owner=ORG, at=f"{ORG_DIR}/travelmanager")
    done = worktree("wt-212", parent, at=f"{parent.path}/{NEST}/wt-212")

    the_plan = planner.plan(state(parent, done, org_repos=("travelmanager",)), wanted())

    assert items_for(the_plan, planner.DISCARD_DIR) == []


def test_a_worktree_discard_also_waits_for_explicit_approval():
    parent = repo("travelmanager", owner=ORG, at=f"{ORG_DIR}/travelmanager")
    done = worktree("wt-212", parent, at=f"{parent.path}/{NEST}/wt-212")

    the_plan = planner.plan(state(parent, done, org_repos=("travelmanager",)), wanted())

    assert the_plan.applicable == ()


# --- dado não decidido não vira plano ----------------------------------------


def test_an_undecided_remote_plans_neither_clone_nor_rewrite():
    the_plan = planner.plan(
        state(repo("travelmanager"), org_repos=("travelmanager", "skills")),
        wanted(remote=None),
    )

    assert items_for(the_plan, planner.CLONE_REPO) == []
    assert items_for(the_plan, planner.REWRITE_REMOTE) == []


def test_an_undecided_migration_list_plans_no_rewrite():
    the_plan = planner.plan(
        state(repo("travelmanager"), org_repos=("travelmanager",)),
        wanted(migrated_from=None),
    )

    assert items_for(the_plan, planner.REWRITE_REMOTE) == []


def test_an_undecided_worktree_layout_moves_no_worktree():
    parent = repo("travelmanager", owner=ORG, at=f"{ORG_DIR}/travelmanager")
    live = worktree("wt-216", parent, branches=(only_here("feat/216"),))

    the_plan = planner.plan(
        state(parent, live, org_repos=("travelmanager",)), wanted(worktrees=None)
    )

    assert items_for(the_plan, planner.MOVE_WORKTREE) == []
    assert items_for(the_plan, planner.REPAIR_WORKTREE) == []


def test_the_preflight_runs_even_with_every_layout_dimension_undecided():
    """Preservar trabalho não depende de decisão de layout nenhuma."""
    the_plan = planner.plan(
        state(repo("campfire", dirty=("notes.md",))),
        Desired(root=ROOT),
    )

    assert targets_for(the_plan, planner.COMMIT_LOCAL) == [f"{ROOT}/campfire"]
