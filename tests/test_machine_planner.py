"""O planner da máquina: de qual estado observado sai qual plano.

Duas decisões desta issue moram aqui e são o motivo de o planner existir:

1. **Negar sempre o alvo resolvido.** A negação em caminho com link bloqueia a
   leitura pela ferramenta e **não** bloqueia o comando de terminal equivalente,
   porque o shell fala com o alvo. Isso foi medido, não deduzido, e o teste que
   codifica o vazamento está aqui.
2. **A remoção do diretório que hospeda o runtime vivo é retida até a migração.**
   Agrupá-la com as outras remoções deixaria a máquina sem `node`. O `hold` é o
   que impede o plano bem-intencionado de inverter o sequenciamento.

As fixtures são estado de máquina, não a máquina real: os casos que importam
(runtime já migrado, negação só pelo link) são estados que a máquina viva não
está hoje, e são exatamente os que precisam de teste.
"""

from panlabs.machine import planner
from panlabs.machine.config import (
    Desired,
    DesiredLink,
    DesiredRetire,
    DesiredSecret,
    DesiredSkills,
    DesiredTool,
    SkillMove,
)
from panlabs.machine.model import (
    CredentialPath,
    Link,
    Observed,
    RetireDir,
    Tool,
    VendoredSkill,
)
from panlabs.plan import Plan, PlanItem

BIN = "/home/op/.local/bin"
SHIMS = "/home/op/.local/share/mise/shims"
NODEENV = "/home/op/.local/share/nodeenvs/campfire-context"
PINNED = "/home/op/.local/bin/ccstatusline"


def items_for(the_plan: Plan, action: str) -> list[PlanItem]:
    return [item for item in the_plan if item.action == action]


def targets_for(the_plan: Plan, action: str) -> list[str]:
    return [item.target for item in items_for(the_plan, action)]


def desired(**overrides: object) -> Desired:
    """Uma configuração desejada inteira e decidida, com só o que o teste mexe."""
    base: dict[str, object] = {
        "bin_dir": BIN,
        "links": (),
        "retire": (),
        "read_denylist": (),
        "statusline": PINNED,
        "skills": DesiredSkills(),
    }
    base.update(overrides)
    return Desired(**base)  # pyright: ignore[reportArgumentType]


# --- negação de leitura: o alvo resolvido, nunca o nome escrito ---------------


def test_a_credential_path_behind_a_symlink_is_denied_on_the_resolved_target():
    state = Observed(
        credentials=(
            CredentialPath(
                path="/home/op/.aws",
                present=True,
                resolved="/mnt/c/Users/op/.aws",
                entries=4,
            ),
        )
    )
    wanted = desired(read_denylist=(DesiredSecret(path="/home/op/.aws", why="chave de 2022"),))

    the_plan = planner.plan(state, wanted)

    assert targets_for(the_plan, planner.DENY_READ) == ["/mnt/c/Users/op/.aws"]


def test_a_denylist_that_names_only_the_symlink_still_plans_the_resolved_target():
    """O vazamento medido: negar o link bloqueia a ferramenta e não bloqueia o shell."""
    state = Observed(
        credentials=(
            CredentialPath(
                path="/home/op/.aws",
                present=True,
                resolved="/mnt/c/Users/op/.aws",
                entries=4,
            ),
        ),
        denylist=("Read(//home/op/.aws/**)",),
    )
    wanted = desired(read_denylist=(DesiredSecret(path="/home/op/.aws", why="chave de 2022"),))

    the_plan = planner.plan(state, wanted)

    assert targets_for(the_plan, planner.DENY_READ) == ["/mnt/c/Users/op/.aws"]


def test_a_denylist_that_already_names_the_resolved_target_plans_nothing():
    state = Observed(
        credentials=(
            CredentialPath(
                path="/home/op/.aws",
                present=True,
                resolved="/mnt/c/Users/op/.aws",
                entries=4,
            ),
        ),
        denylist=("Read(//mnt/c/Users/op/.aws/**)",),
    )
    wanted = desired(read_denylist=(DesiredSecret(path="/home/op/.aws", why="chave de 2022"),))

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.DENY_READ) == []


def test_two_desired_paths_resolving_to_one_target_collapse_into_one_denial():
    state = Observed(
        credentials=(
            CredentialPath(
                path="/home/op/.aws", present=True, resolved="/mnt/c/Users/op/.aws", entries=4
            ),
            CredentialPath(
                path="/mnt/c/Users/op/.aws",
                present=True,
                resolved="/mnt/c/Users/op/.aws",
                entries=4,
            ),
        )
    )
    wanted = desired(
        read_denylist=(
            DesiredSecret(path="/home/op/.aws", why="pelo link"),
            DesiredSecret(path="/mnt/c/Users/op/.aws", why="pelo alvo"),
        )
    )

    the_plan = planner.plan(state, wanted)

    assert targets_for(the_plan, planner.DENY_READ) == ["/mnt/c/Users/op/.aws"]


def test_an_absent_credential_path_is_not_denied():
    state = Observed(credentials=(CredentialPath(path="/home/op/.azure", present=False),))
    wanted = desired(read_denylist=(DesiredSecret(path="/home/op/.azure", why="nuvem"),))

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.DENY_READ) == []


def test_an_empty_credential_dir_is_denied_by_anticipation_and_says_so():
    """O raio real são as credenciais que existem; o plano não pode inflá-lo."""
    state = Observed(
        credentials=(
            CredentialPath(
                path="/home/op/secrets", present=True, resolved="/home/op/secrets", entries=0
            ),
        )
    )
    wanted = desired(read_denylist=(DesiredSecret(path="/home/op/secrets", why="cofre"),))

    the_plan = planner.plan(state, wanted)

    (item,) = items_for(the_plan, planner.DENY_READ)
    assert "vazio" in item.reason


def test_a_credential_file_is_denied_without_the_recursive_suffix():
    state = Observed(
        credentials=(
            CredentialPath(
                path="/home/op/.claude/.credentials.json",
                present=True,
                resolved="/home/op/.claude/.credentials.json",
                is_dir=False,
                entries=1,
            ),
        )
    )
    wanted = desired(
        read_denylist=(
            DesiredSecret(path="/home/op/.claude/.credentials.json", why="token do agente"),
        )
    )

    the_plan = planner.plan(state, wanted)

    (item,) = items_for(the_plan, planner.DENY_READ)
    assert item.payload["entry"] == "Read(//home/op/.claude/.credentials.json)"


# --- o sequenciamento que não pode ser invertido ------------------------------


def test_removing_the_dir_that_hosts_the_live_runtime_is_planned_but_held():
    state = Observed(
        links=(Link(name="node", points_to=f"{NODEENV}/bin/node", resolved=f"{NODEENV}/bin/node"),),
        retire=(RetireDir(path=NODEENV, present=True, bytes=1_000_000_000),),
    )
    wanted = desired(
        links=(DesiredLink(name="node", target=f"{SHIMS}/node", why="runtime gerido"),),
        retire=(DesiredRetire(path=NODEENV, why="runtime não depende de nome de projeto"),),
    )

    the_plan = planner.plan(state, wanted)

    (item,) = items_for(the_plan, planner.RETIRE_DIR)
    assert item.hold
    assert "node" in item.hold


def test_the_same_dir_is_free_to_remove_once_the_runtime_resolves_elsewhere():
    state = Observed(
        links=(Link(name="node", points_to=f"{SHIMS}/node", resolved=f"{SHIMS}/node"),),
        retire=(RetireDir(path=NODEENV, present=True, bytes=1_000_000_000),),
    )
    wanted = desired(
        links=(DesiredLink(name="node", target=f"{SHIMS}/node", why="runtime gerido"),),
        retire=(DesiredRetire(path=NODEENV, why="runtime não depende de nome de projeto"),),
    )

    the_plan = planner.plan(state, wanted)

    (item,) = items_for(the_plan, planner.RETIRE_DIR)
    assert not item.hold


def test_a_ghost_manager_is_never_held_because_nothing_resolves_inside_it():
    state = Observed(
        links=(Link(name="node", points_to=f"{NODEENV}/bin/node", resolved=f"{NODEENV}/bin/node"),),
        retire=(RetireDir(path="/home/op/.pyenv", present=True, bytes=1_800_000_000),),
    )
    wanted = desired(
        links=(DesiredLink(name="node", target=f"{SHIMS}/node", why="runtime gerido"),),
        retire=(DesiredRetire(path="/home/op/.pyenv", why="fantasma fora do PATH"),),
    )

    the_plan = planner.plan(state, wanted)

    (item,) = items_for(the_plan, planner.RETIRE_DIR)
    assert not item.hold


def test_a_dir_already_absent_is_not_planned_for_removal():
    state = Observed(retire=(RetireDir(path="/home/op/.nvm", present=False),))
    wanted = desired(retire=(DesiredRetire(path="/home/op/.nvm", why="fantasma sem versão"),))

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.RETIRE_DIR) == []


# --- nomes alcançáveis em subprocesso ----------------------------------------


def test_a_name_that_does_not_exist_in_the_bin_dir_is_planned_as_a_link():
    state = Observed(links=(Link(name="fd"),))
    wanted = desired(
        links=(DesiredLink(name="fd", target="/usr/bin/fdfind", why="alias não vale subprocesso"),)
    )

    the_plan = planner.plan(state, wanted)

    assert targets_for(the_plan, planner.LINK_NAME) == [f"{BIN}/fd"]


def test_a_name_pointing_at_the_wrong_target_is_planned_as_a_relink():
    state = Observed(
        links=(Link(name="node", points_to=f"{NODEENV}/bin/node", resolved=f"{NODEENV}/bin/node"),)
    )
    wanted = desired(
        links=(DesiredLink(name="node", target=f"{SHIMS}/node", why="runtime gerido"),)
    )

    the_plan = planner.plan(state, wanted)

    (item,) = items_for(the_plan, planner.LINK_NAME)
    assert item.payload["target"] == f"{SHIMS}/node"


def test_a_name_already_pointing_at_the_desired_target_plans_nothing():
    state = Observed(
        links=(Link(name="fd", points_to="/usr/bin/fdfind", resolved="/usr/bin/fdfind"),)
    )
    wanted = desired(
        links=(DesiredLink(name="fd", target="/usr/bin/fdfind", why="alias não vale subprocesso"),)
    )

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.LINK_NAME) == []


def test_a_name_pointing_where_asked_but_anchored_on_its_own_dir_is_reported_unreachable():
    """O defeito medido: o link estava exatamente onde o dado pedia e o nome não rodava.

    O shim do pacote calculava o que executar a partir do próprio diretório, e
    alcançado pelo link passou a procurar o pacote ao lado do link. Conferir só o
    alvo imediato aprova este estado e deixa o nome morto, que foi o que
    aconteceu com a barra de status.
    """
    target = "/home/op/.local/share/mise/installs/npm-ccstatusline/latest/node_modules/.bin/cc"
    state = Observed(
        links=(
            Link(
                name="ccstatusline",
                points_to=target,
                resolved=target,
                anchored_target=True,
            ),
        )
    )
    wanted = desired(
        links=(DesiredLink(name="ccstatusline", target=target, why="a barra de status"),)
    )

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.LINK_NAME) == []
    (item,) = items_for(the_plan, planner.UNREACHABLE_NAME)
    assert item.target == f"{BIN}/ccstatusline"
    assert item.hold


def test_an_unreachable_name_is_never_fixed_by_relinking_it():
    """Refazer o link reproduz o mesmo alvo, e o alvo é o defeito."""
    target = "/home/op/.local/share/mise/installs/npm-ccstatusline/latest/node_modules/.bin/cc"
    state = Observed(
        links=(Link(name="ccstatusline", points_to=target, resolved=target, anchored_target=True),)
    )
    wanted = desired(
        links=(DesiredLink(name="ccstatusline", target=target, why="a barra de status"),)
    )

    the_plan = planner.plan(state, wanted)

    assert planner.UNREACHABLE_NAME in planner.MANUAL_ACTIONS
    assert targets_for(the_plan, planner.LINK_NAME) == []


def test_a_name_pointing_at_a_relocatable_target_is_not_reported_unreachable():
    """O shim do gerenciador de runtime é binário: ele resolve pelo nome, não pelo diretório."""
    state = Observed(
        links=(Link(name="node", points_to=f"{SHIMS}/node", resolved=f"{SHIMS}/node"),)
    )
    wanted = desired(
        links=(DesiredLink(name="node", target=f"{SHIMS}/node", why="runtime gerido"),)
    )

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.UNREACHABLE_NAME) == []


# --- a barra de status não baixa nada por render ------------------------------


def test_a_statusline_that_fetches_on_every_render_is_planned_for_replacement():
    state = Observed(statusline="npx ccstatusline@latest")
    wanted = desired(statusline=PINNED)

    the_plan = planner.plan(state, wanted)

    assert targets_for(the_plan, planner.PIN_STATUSLINE) == ["statusLine"]


def test_a_statusline_already_pinned_plans_nothing():
    state = Observed(statusline=PINNED)
    wanted = desired(statusline=PINNED)

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.PIN_STATUSLINE) == []


# --- zero redundância de skills ----------------------------------------------


def test_a_real_orphan_absent_from_the_global_is_planned_for_promotion():
    state = Observed(
        global_skills=("tdd",),
        vendored_skills=(VendoredSkill(repo="panlabs", name="caveman", path="/w/panlabs/caveman"),),
    )
    wanted = desired(
        skills=DesiredSkills(
            promote=(SkillMove(name="caveman", source="panlabs", why="órfã real"),),
        )
    )

    the_plan = planner.plan(state, wanted)

    assert targets_for(the_plan, planner.PROMOTE_SKILL) == ["caveman"]


def test_an_old_revision_of_an_existing_global_is_discarded_not_promoted():
    state = Observed(
        global_skills=("to-spec",),
        vendored_skills=(VendoredSkill(repo="panlabs", name="to-prd", path="/w/panlabs/to-prd"),),
    )
    wanted = desired(
        skills=DesiredSkills(
            discard=(
                SkillMove(
                    name="to-prd",
                    source="panlabs",
                    why="revisão anterior",
                    superseded_by="to-spec",
                ),
            ),
        )
    )

    the_plan = planner.plan(state, wanted)

    (item,) = items_for(the_plan, planner.DISCARD_SKILL)
    assert item.target == "to-prd"
    assert items_for(the_plan, planner.PROMOTE_SKILL) == []
    # Descartar já está realizado por `to-prd` não existir no global. Aplicar não
    # tem o que fazer, e o arquivo no repo é o retrofit da spec de Repo #4.
    assert item.hold


def test_a_skill_already_in_the_global_is_not_promoted_twice():
    state = Observed(
        global_skills=("caveman",),
        vendored_skills=(VendoredSkill(repo="panlabs", name="caveman", path="/w/panlabs/caveman"),),
    )
    wanted = desired(
        skills=DesiredSkills(
            promote=(SkillMove(name="caveman", source="panlabs", why="órfã real"),),
        )
    )

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.PROMOTE_SKILL) == []


def test_a_vendored_copy_of_a_global_skill_is_found_by_the_scan():
    state = Observed(
        global_skills=("tdd",),
        vendored_skills=(VendoredSkill(repo="panlabs", name="tdd", path="/w/panlabs/tdd"),),
    )
    wanted = desired(skills=DesiredSkills())

    the_plan = planner.plan(state, wanted)

    (item,) = items_for(the_plan, planner.DROP_VENDORED_SKILL)
    assert item.target == "/w/panlabs/tdd"


def test_every_vendored_copy_the_scan_finds_is_shown_but_held():
    """Remover arquivo de dentro de um repo e o retrofit da spec de Repo #4."""
    state = Observed(
        global_skills=("tdd",),
        vendored_skills=(
            VendoredSkill(repo="panlabs", name="tdd", path="/w/panlabs/tdd"),
            VendoredSkill(repo="travelmanager", name="tdd", path="/w/tm/tdd"),
        ),
    )
    wanted = desired(skills=DesiredSkills())

    the_plan = planner.plan(state, wanted)

    found = items_for(the_plan, planner.DROP_VENDORED_SKILL)
    assert len(found) == 2
    assert all(item.hold for item in found)


def test_a_skill_that_exists_only_in_a_repo_is_not_touched_by_the_clause():
    """A cláusula é sobre colisão com o global, não sobre skill local legítima."""
    state = Observed(
        global_skills=("tdd",),
        vendored_skills=(
            VendoredSkill(repo="panlabs", name="repo-specific", path="/w/panlabs/repo-specific"),
        ),
    )
    wanted = desired(skills=DesiredSkills())

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.DROP_VENDORED_SKILL) == []


def test_a_skill_being_promoted_now_counts_as_global_for_the_clause():
    """Promover sem des-vendorizar criaria a inversão de precedência que a cláusula dissolve."""
    state = Observed(
        global_skills=(),
        vendored_skills=(
            VendoredSkill(repo="panlabs", name="caveman", path="/w/panlabs/caveman"),
            VendoredSkill(repo="travelmanager", name="caveman", path="/w/tm/caveman"),
        ),
    )
    wanted = desired(
        skills=DesiredSkills(
            promote=(SkillMove(name="caveman", source="panlabs", why="órfã real"),),
        )
    )

    the_plan = planner.plan(state, wanted)

    assert sorted(targets_for(the_plan, planner.DROP_VENDORED_SKILL)) == [
        "/w/panlabs/caveman",
        "/w/tm/caveman",
    ]


# --- dado não decidido não vira plano ----------------------------------------


def test_an_undecided_dimension_plans_nothing_for_itself():
    state = Observed(
        links=(Link(name="fd"),),
        credentials=(
            CredentialPath(
                path="/home/op/.aws", present=True, resolved="/mnt/c/Users/op/.aws", entries=4
            ),
        ),
    )
    wanted = Desired(bin_dir=BIN, links=None, read_denylist=None)

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.LINK_NAME) == []
    assert items_for(the_plan, planner.DENY_READ) == []


def test_a_fully_converged_machine_produces_an_empty_plan():
    state = Observed(
        links=(Link(name="fd", points_to="/usr/bin/fdfind", resolved="/usr/bin/fdfind"),),
        retire=(RetireDir(path="/home/op/.nvm", present=False),),
        credentials=(
            CredentialPath(path="/home/op/.ssh", present=True, resolved="/home/op/.ssh", entries=6),
        ),
        denylist=("Read(//home/op/.ssh/**)",),
        statusline=PINNED,
        global_skills=("tdd",),
    )
    wanted = desired(
        links=(DesiredLink(name="fd", target="/usr/bin/fdfind", why="subprocesso"),),
        retire=(DesiredRetire(path="/home/op/.nvm", why="fantasma"),),
        read_denylist=(DesiredSecret(path="/home/op/.ssh", why="chaves privadas"),),
    )

    the_plan = planner.plan(state, wanted)

    assert len(the_plan) == 0


def test_a_link_whose_target_is_itself_a_symlink_is_not_replanned_forever():
    """O gerenciador de runtime mantém um `latest` que reaponta a cada upgrade.

    Comparar pelo fim da cadeia veria a versão concreta, nunca o `latest` pedido,
    e o plano pediria o mesmo relink em toda rodada. É o alvo imediato que responde
    "este nome aponta para onde eu pedi".
    """
    state = Observed(
        links=(
            Link(
                name="ccstatusline",
                points_to=f"{SHIMS}/../installs/npm-ccstatusline/latest/bin/ccstatusline",
                resolved="/home/op/.local/share/mise/installs/npm-ccstatusline/2.2.25/bin/cc",
            ),
        )
    )
    wanted = desired(
        links=(
            DesiredLink(
                name="ccstatusline",
                target=f"{SHIMS}/../installs/npm-ccstatusline/latest/bin/ccstatusline",
                why="a barra de status não baixa nada por render",
            ),
        )
    )

    the_plan = planner.plan(state, wanted)

    assert items_for(the_plan, planner.LINK_NAME) == []


def test_promotion_reads_from_the_declared_source_repo_not_whichever_scan_saw_last():
    """A mesma skill existe em muitos repos; promover é ler do repo que o dado nomeia.

    Sem casar repo e nome, a última cópia varrida ganharia, e a origem da skill
    global passaria a depender da ordem alfabética do disco.
    """
    state = Observed(
        global_skills=(),
        vendored_skills=(
            VendoredSkill(repo="panlabs", name="caveman", path="/w/panlabs/caveman"),
            VendoredSkill(repo="wt-216", name="caveman", path="/w/wt-216/caveman"),
        ),
    )
    wanted = desired(
        skills=DesiredSkills(
            promote=(SkillMove(name="caveman", source="panlabs", why="órfã real"),)
        )
    )

    the_plan = planner.plan(state, wanted)

    (item,) = items_for(the_plan, planner.PROMOTE_SKILL)
    assert item.payload["from"] == "/w/panlabs/caveman"
    assert "panlabs" in item.reason


# --- o portão local: a ferramenta que executa a declaração de cada repo --------


def tool(name: str = "lefthook", **overrides: object) -> DesiredTool:
    base: dict[str, object] = {
        "name": name,
        "install": f"gh release download --repo x/{name}",
        "why": "o binário que executa a declaração versionada de cada repo",
    }
    base.update(overrides)
    return DesiredTool(**base)  # pyright: ignore[reportArgumentType]


def test_a_declared_tool_that_the_machine_does_not_have_is_planned():
    """O caso vivo: `lefthook.yml` em todo repo da frota, e nenhum hook armado.

    O portão 1 era declaração inerte em 100% dos clones, e o convergedor de máquina
    não tinha como saber que o binário é equipamento dele: nenhuma chave do dado o
    nomeava, então nenhum plano jamais o mencionou.
    """
    state = Observed(tools=(Tool(name="lefthook"),))

    the_plan = planner.plan(state, desired(tools=(tool(),)))

    assert targets_for(the_plan, planner.INSTALL_TOOL) == ["lefthook"]


def test_the_plan_carries_the_exact_command_because_nothing_here_runs_it():
    """Como em `promote-skill`: o método é do próprio binário, não deste applier.

    Um plano que dissesse apenas "instale o lefthook" empurraria de volta para quem
    lê a decisão que `docs/maquina.md` já tomou por classe.
    """
    state = Observed(tools=(Tool(name="lefthook"),))

    item = items_for(planner.plan(state, desired(tools=(tool(),))), planner.INSTALL_TOOL)[0]

    assert item.payload["install"] == "gh release download --repo x/lefthook"


def test_a_tool_the_machine_already_resolves_is_not_planned():
    """`gitleaks` já está em `~/.local/bin`, e convergido não vira item."""
    state = Observed(tools=(Tool(name="gitleaks", resolved="/home/op/.local/bin/gitleaks"),))

    the_plan = planner.plan(state, desired(tools=(tool("gitleaks"),)))

    assert items_for(the_plan, planner.INSTALL_TOOL) == []


def test_a_tool_dimension_never_decided_plans_nothing():
    """`null` no dado é ausência de pergunta, e o planner não responde por ninguém."""
    state = Observed(tools=(Tool(name="lefthook"),))

    the_plan = planner.plan(state, desired(tools=None))

    assert items_for(the_plan, planner.INSTALL_TOOL) == []


def test_the_reason_names_the_tool_and_why_it_is_equipment():
    state = Observed(tools=(Tool(name="lefthook"),))

    item = items_for(planner.plan(state, desired(tools=(tool(),))), planner.INSTALL_TOOL)[0]

    assert "executa a declaração versionada" in item.reason
    assert "não resolve" in item.reason


# --- a promoção que não pode depender de a cópia ainda estar no repo -----------


def test_a_promotion_survives_the_retrofit_that_removed_the_vendored_copy():
    """O caso vivo, e o mais caro: a capacidade não está em lugar nenhum.

    O retrofit do `panlabs` removeu as três cópias vendorizadas, que era o objetivo
    dele. A partir daquele merge as três promoções sumiram do plano sem que nada
    acusasse, porque a origem era usada como condição em vez de procedência.

    A urgência é o inverso do que o código antigo assumia: enquanto a skill estava
    no repo, a capacidade existia em algum lugar. Depois da remoção ela não existe
    em lugar nenhum, e é esse o estado em que o plano precisa gritar.
    """
    state = Observed(global_skills=(), vendored_skills=())
    wanted = desired(
        skills=DesiredSkills(promote=(SkillMove(name="caveman", source="panlabs", why="órfã"),))
    )

    the_plan = planner.plan(state, wanted)

    assert targets_for(the_plan, planner.PROMOTE_SKILL) == ["caveman"]


def test_the_reason_says_the_source_is_gone_because_that_changes_what_to_do():
    """Sobe de um repo e sobe do nada são urgências diferentes, e o motivo as separa."""
    state = Observed(global_skills=(), vendored_skills=())
    wanted = desired(
        skills=DesiredSkills(promote=(SkillMove(name="caveman", source="panlabs", why="órfã"),))
    )

    item = items_for(planner.plan(state, wanted), planner.PROMOTE_SKILL)[0]

    assert "não está mais em panlabs" in item.reason


def test_a_promotion_whose_source_still_exists_still_names_where_it_comes_from():
    """O caminho antigo não se perde: quando há origem, ela continua no motivo."""
    state = Observed(
        global_skills=(),
        vendored_skills=(VendoredSkill(repo="panlabs", name="caveman", path="/w/panlabs/caveman"),),
    )
    wanted = desired(
        skills=DesiredSkills(promote=(SkillMove(name="caveman", source="panlabs", why="órfã"),))
    )

    item = items_for(planner.plan(state, wanted), planner.PROMOTE_SKILL)[0]

    assert "sobe de panlabs" in item.reason
    assert item.payload["from"] == "/w/panlabs/caveman"


def test_a_skill_already_in_the_global_is_never_promoted_even_without_a_source():
    """O critério é `não está no global`, e ele continua sendo o único."""
    state = Observed(global_skills=("caveman",), vendored_skills=())
    wanted = desired(
        skills=DesiredSkills(promote=(SkillMove(name="caveman", source="panlabs", why="órfã"),))
    )

    assert items_for(planner.plan(state, wanted), planner.PROMOTE_SKILL) == []


def test_a_discard_still_needs_the_copy_to_exist_because_there_is_nothing_to_remove():
    """Descarte é o oposto: sem cópia no repo, a decisão já está realizada.

    Simetria aqui seria erro. Promover sem origem é urgente; descartar sem origem
    não tem alvo.
    """
    state = Observed(global_skills=("to-spec",), vendored_skills=())
    wanted = desired(
        skills=DesiredSkills(
            discard=(
                SkillMove(
                    name="to-prd", source="panlabs", why="revisão anterior", superseded_by="to-spec"
                ),
            )
        )
    )

    assert items_for(planner.plan(state, wanted), planner.DISCARD_SKILL) == []
