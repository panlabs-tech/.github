"""O planner do heartbeat: de qual estado observado sai qual plano.

Quatro decisões desta issue moram aqui, e são o motivo de o planner existir:

1. **O ramo é do estado, não do calendário.** Poda exige o WSL de pé, compactação
   exige o WSL parado, e a tarefa nunca liga nem desliga nada. O que ela faz é o
   que for seguro agora.
2. **Disparo diário não é cadência da ação.** O disparo existe para dar ~30
   chances por mês de encontrar o WSL no estado certo. Cada passo tem a cadência
   dele, e um passo cujo prazo não venceu não entra no plano.
3. **Cada passo tem canal de alarme próprio.** Falha num passo de rede não pode
   se disfarçar de alarme de disco, porque o alarme de disco é o único vigia de
   uma métrica que não se mede de dentro do WSL.
4. **Versão velha de browser é o desperdício; browser não é.** Manter a revisão
   mais nova de cada família custa quase nada e não quebra o próximo teste.

As fixtures são estado de máquina sintético: os casos que importam (WSL parado,
marca velha, disco abaixo do piso) são estados que a máquina viva não está agora,
e são exatamente os que precisam de teste.
"""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from panlabs.heartbeat import planner
from panlabs.heartbeat.config import (
    Desired,
    DesiredChannel,
    DesiredFloor,
    DesiredStale,
    DesiredStep,
    DesiredUnobserved,
    DropMatching,
    KeepNewest,
    Report,
)
from panlabs.heartbeat.model import (
    BRANCH_DOWN,
    BRANCH_UP,
    CacheVersion,
    HostDisk,
    LeftoverFile,
    Mark,
    Observed,
)
from panlabs.plan import Plan, PlanItem

NOW = datetime(2026, 7, 25, 3, 0, tzinfo=UTC)
GIGA = 1_000_000_000
FLOOR = 25 * GIGA
PLAYWRIGHT = "/home/op/.cache/ms-playwright"
PUPPETEER = "/home/op/.cache/puppeteer"


def days_ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def items_for(the_plan: Plan, action: str) -> list[PlanItem]:
    return [item for item in the_plan if item.action == action]


def targets_for(the_plan: Plan, action: str) -> list[str]:
    return [item.target for item in items_for(the_plan, action)]


def channels_for(items: Iterable[PlanItem]) -> list[str]:
    return [str(item.payload.get("alarm", "")) for item in items]


def prune(**overrides: object) -> DesiredStep:
    base: dict[str, object] = {
        "name": "npm",
        "branch": BRANCH_UP,
        "every_days": 7,
        "alarm": "falha",
        "why": "o cache do npm é o maior consumidor e não mora em ~/.cache",
        "run": ("npm", "cache", "verify"),
    }
    base.update(overrides)
    return DesiredStep(**base)  # pyright: ignore[reportArgumentType]


def compact(**overrides: object) -> DesiredStep:
    base: dict[str, object] = {
        "name": "compact-vhdx",
        "branch": BRANCH_DOWN,
        "every_days": 30,
        "alarm": "falha",
        "why": "o único caminho de compactação nesta edição do Windows",
        "on_host": True,
    }
    base.update(overrides)
    return DesiredStep(**base)  # pyright: ignore[reportArgumentType]


def desired(**overrides: object) -> Desired:
    """Uma configuração desejada inteira e decidida, com só o que o teste mexe."""
    base: dict[str, object] = {
        "channels": (
            DesiredChannel(name="falha", why="um passo falhou"),
            DesiredChannel(name="disco", why="o disco do host cruzou o piso"),
            DesiredChannel(name="marca", why="a tarefa parou de rodar"),
        ),
        "host_floor": DesiredFloor(free_bytes=FLOOR, alarm="disco", why="~2 meses de folga"),
        "stale_mark": DesiredStale(after_days=3, alarm="marca", why="o disparo é diário"),
        "unobserved": DesiredUnobserved(alarm="falha", why="não observado é falha"),
        "steps": (prune(), compact()),
    }
    base.update(overrides)
    return Desired(**base)  # pyright: ignore[reportArgumentType]


def healthy(**overrides: object) -> Observed:
    """Uma máquina saudável: WSL de pé, disco folgado, tudo rodado ontem."""
    base: dict[str, object] = {
        "now": NOW,
        "wsl_running": True,
        "host": HostDisk(measured=True, free_bytes=60 * GIGA, total_bytes=490 * GIGA),
        "last_run": days_ago(1),
        "marks": (Mark(step="npm", at=days_ago(1)), Mark(step="compact-vhdx", at=days_ago(1))),
    }
    base.update(overrides)
    return Observed(**base)  # pyright: ignore[reportArgumentType]


# --- o ramo é do estado observado, e a tarefa nunca liga nem desliga nada ------


def test_with_the_wsl_running_the_plan_prunes_and_does_not_compact():
    state = healthy(marks=())

    the_plan = planner.plan(state, desired())

    assert targets_for(the_plan, planner.RUN_STEP) == ["npm"]
    assert items_for(the_plan, planner.RUN_ON_HOST) == []


def test_with_the_wsl_stopped_the_plan_compacts_and_does_not_prune():
    state = healthy(wsl_running=False, marks=())

    the_plan = planner.plan(state, desired())

    assert targets_for(the_plan, planner.RUN_ON_HOST) == ["compact-vhdx"]
    assert items_for(the_plan, planner.RUN_STEP) == []


def test_an_unconsulted_wsl_state_plans_no_step_at_all():
    """Tratar não consultado como parado rodaria a compactação contra um disco vivo."""
    state = healthy(wsl_running=None, marks=())

    the_plan = planner.plan(state, desired())

    assert items_for(the_plan, planner.RUN_STEP) == []


def test_an_unconsulted_wsl_state_is_reported_instead_of_passing_silently():
    state = healthy(wsl_running=None, marks=())

    the_plan = planner.plan(state, desired())

    assert channels_for(items_for(the_plan, planner.NOTIFY)) == ["falha"]


# --- disparo diário não é cadência da ação ------------------------------------


def test_a_step_whose_cadence_has_not_elapsed_stays_out_of_the_plan():
    """O disparo é diário; a cadência do passo é de sete dias, e ela é que manda."""
    state = healthy(marks=(Mark(step="npm", at=days_ago(3)),))

    the_plan = planner.plan(state, desired())

    assert items_for(the_plan, planner.RUN_STEP) == []


def test_a_step_whose_cadence_has_elapsed_enters_the_plan():
    state = healthy(marks=(Mark(step="npm", at=days_ago(8)),))

    the_plan = planner.plan(state, desired())

    assert targets_for(the_plan, planner.RUN_STEP) == ["npm"]


def test_a_step_that_never_ran_is_due_on_the_first_trigger():
    state = healthy(marks=())

    the_plan = planner.plan(state, desired())

    assert "nunca rodou" in items_for(the_plan, planner.RUN_STEP)[0].reason


def test_two_steps_on_the_same_branch_keep_separate_cadences():
    """A cadência é do passo: o barato roda semanal, o caro espera o mês."""
    wipe = prune(name="pip", every_days=30, run=("pip", "cache", "purge"))
    state = healthy(
        marks=(Mark(step="npm", at=days_ago(8)), Mark(step="pip", at=days_ago(8))),
    )

    the_plan = planner.plan(state, desired(steps=(prune(), wipe)))

    assert targets_for(the_plan, planner.RUN_STEP) == ["npm"]


# --- o hospedeiro: um passo plugado entra sem reescrita -----------------------


def test_a_plugged_step_lands_on_the_branch_it_declares():
    """A prova de que o checker de conformidade da spec de Repo #4 entra como dado.

    Ele declara ramo, cadência e canal; nada no planner sabe que ele existe.
    """
    checker = DesiredStep(
        name="checker",
        branch=BRANCH_UP,
        every_days=1,
        alarm="conformidade",
        why="a deriva de anatomia da frota é alarme, não gate de PR",
        run=("uv", "run", "panlabs-checker"),
    )
    wanted = desired(
        channels=(
            DesiredChannel(name="falha", why="um passo falhou"),
            DesiredChannel(name="conformidade", why="a frota derivou da anatomia"),
        ),
        steps=(prune(), compact(), checker),
    )

    up = planner.plan(healthy(marks=()), wanted)
    down = planner.plan(healthy(wsl_running=False, marks=()), wanted)

    assert targets_for(up, planner.RUN_STEP) == ["npm", "checker"]
    assert targets_for(down, planner.RUN_ON_HOST) == ["compact-vhdx"]


def test_a_report_step_carries_the_whole_code_to_channel_map_into_the_plan():
    """O applier não decide o canal: ele lê o mapa que o planner escreveu no item.

    O código de saída só existe depois de o comando rodar, então o mapa inteiro
    precisa atravessar. O que o applier faz é consulta em tabela, não decisão.
    """
    checker = prune(
        name="checker",
        run=(),
        alarm="falha",
        report=Report(command=("panlabs-checker",), codes={1: "anatomia", 2: "falha"}),
    )
    wanted = desired(
        channels=(
            DesiredChannel(name="falha", why="um passo falhou"),
            DesiredChannel(name="anatomia", why="a frota derivou da anatomia"),
        ),
        steps=(checker,),
    )

    the_plan = planner.plan(healthy(marks=()), wanted)

    item = items_for(the_plan, planner.REPORT_STEP)[0]
    assert item.target == "checker"
    assert item.payload["codes"] == {"1": "anatomia", "2": "falha"}
    assert item.payload["run"] == ["panlabs-checker"]


def test_a_report_step_keeps_its_own_channel_for_the_codes_nobody_declared():
    """Um código fora do mapa é falha do passo, e falha de passo é do canal dele."""
    checker = prune(
        name="checker",
        run=(),
        alarm="falha",
        report=Report(command=("panlabs-checker",), codes={1: "anatomia"}),
    )
    wanted = desired(
        channels=(
            DesiredChannel(name="falha", why="um passo falhou"),
            DesiredChannel(name="anatomia", why="a frota derivou da anatomia"),
        ),
        steps=(checker,),
    )

    the_plan = planner.plan(healthy(marks=()), wanted)

    assert items_for(the_plan, planner.REPORT_STEP)[0].payload["alarm"] == "falha"


def test_a_report_step_respects_its_cadence_like_any_other_step():
    checker = prune(
        name="checker",
        run=(),
        every_days=1,
        report=Report(command=("panlabs-checker",), codes={1: "falha"}),
    )
    state = healthy(marks=(Mark(step="checker", at=days_ago(0.5)),))

    the_plan = planner.plan(state, desired(steps=(checker,)))

    assert items_for(the_plan, planner.REPORT_STEP) == []


def test_a_plugged_step_carries_its_own_alarm_channel_and_not_the_disk_one():
    """Falha de token num passo de rede não pode se disfarçar de alarme de disco."""
    checker = prune(name="checker", alarm="conformidade", run=("uv", "run", "panlabs-checker"))
    wanted = desired(
        channels=(
            DesiredChannel(name="falha", why="um passo falhou"),
            DesiredChannel(name="disco", why="o disco do host cruzou o piso"),
            DesiredChannel(name="conformidade", why="a frota derivou"),
        ),
        steps=(prune(), checker),
    )
    state = healthy(marks=(), host=HostDisk(measured=True, free_bytes=GIGA, total_bytes=490 * GIGA))

    the_plan = planner.plan(state, wanted)

    by_target = {item.target: item.payload.get("alarm") for item in the_plan}
    assert by_target["checker"] == "conformidade"
    assert by_target["npm"] == "falha"
    assert by_target["disco do host"] == "disco"


# --- os alarmes ---------------------------------------------------------------


def test_host_disk_below_the_floor_produces_a_notification():
    state = healthy(host=HostDisk(measured=True, free_bytes=20 * GIGA, total_bytes=490 * GIGA))

    the_plan = planner.plan(state, desired())

    assert targets_for(the_plan, planner.NOTIFY) == ["disco do host"]


def test_a_host_disk_above_the_floor_is_silent():
    the_plan = planner.plan(healthy(), desired())

    assert items_for(the_plan, planner.NOTIFY) == []


def test_a_host_disk_that_could_not_be_measured_does_not_look_like_a_full_disk():
    """Zero não medido dispararia o piso justamente quando ninguém mediu nada."""
    state = healthy(host=HostDisk(measured=False))

    the_plan = planner.plan(state, desired())

    assert targets_for(the_plan, planner.NOTIFY) == ["disco do host"]
    assert channels_for(items_for(the_plan, planner.NOTIFY)) == ["falha"]


def test_a_stale_run_mark_produces_a_notification():
    state = healthy(last_run=days_ago(5))

    the_plan = planner.plan(state, desired())

    assert targets_for(the_plan, planner.NOTIFY) == ["marca de execução"]


def test_a_missing_run_mark_is_the_first_trigger_and_not_an_alarm():
    """Alarmar no primeiro disparo treinaria o operador a ignorar o canal."""
    state = healthy(last_run=None, marks=())

    the_plan = planner.plan(state, desired())

    assert items_for(the_plan, planner.NOTIFY) == []


def test_a_healthy_machine_produces_an_empty_plan():
    """Silencioso quando saudável: é isso que faz notificação significar alguma coisa."""
    assert planner.plan(healthy(), desired()) == Plan()


def test_the_alarms_come_before_the_steps_so_a_hung_step_cannot_swallow_them():
    state = healthy(
        marks=(),
        host=HostDisk(measured=True, free_bytes=GIGA, total_bytes=490 * GIGA),
    )

    the_plan = planner.plan(state, desired())

    assert [item.action for item in the_plan] == [planner.NOTIFY, planner.RUN_STEP]


# --- versão velha de browser é o desperdício, browser não é -------------------


def test_obsolete_browser_versions_are_dropped_and_the_newest_is_kept():
    step = prune(name="playwright", run=(), keep_newest=KeepNewest(root=PLAYWRIGHT, keep=1))
    state = healthy(
        marks=(),
        versions=(
            CacheVersion(
                PLAYWRIGHT, "chromium", (1161,), f"{PLAYWRIGHT}/chromium-1161", 800 * 10**6
            ),
            CacheVersion(
                PLAYWRIGHT, "chromium", (1223,), f"{PLAYWRIGHT}/chromium-1223", 800 * 10**6
            ),
            CacheVersion(
                PLAYWRIGHT, "chromium", (1169,), f"{PLAYWRIGHT}/chromium-1169", 800 * 10**6
            ),
        ),
    )

    the_plan = planner.plan(state, desired(steps=(step,)))

    assert targets_for(the_plan, planner.DROP_DIR) == [
        f"{PLAYWRIGHT}/chromium-1161",
        f"{PLAYWRIGHT}/chromium-1169",
    ]


def test_a_version_is_ranked_by_number_and_not_alphabetically():
    """`148.0.7778.97` está acima de `127.0.6533.72`, e a ordem de texto diria o contrário."""
    step = prune(name="puppeteer", run=(), keep_newest=KeepNewest(root=PUPPETEER, keep=1))
    state = healthy(
        marks=(),
        versions=(
            CacheVersion(PUPPETEER, "chrome/linux", (148, 0, 7778, 97), f"{PUPPETEER}/a"),
            CacheVersion(PUPPETEER, "chrome/linux", (127, 0, 6533, 72), f"{PUPPETEER}/b"),
        ),
    )

    the_plan = planner.plan(state, desired(steps=(step,)))

    assert targets_for(the_plan, planner.DROP_DIR) == [f"{PUPPETEER}/b"]


def test_two_products_sharing_a_version_prefix_do_not_prune_each_other():
    """`chrome/linux-148` e `chrome-headless-shell/linux-148` são famílias distintas."""
    step = prune(name="puppeteer", run=(), keep_newest=KeepNewest(root=PUPPETEER, keep=1))
    state = healthy(
        marks=(),
        versions=(
            CacheVersion(PUPPETEER, "chrome/linux", (148,), f"{PUPPETEER}/chrome/linux-148"),
            CacheVersion(PUPPETEER, "shell/linux", (127,), f"{PUPPETEER}/shell/linux-127"),
        ),
    )

    the_plan = planner.plan(state, desired(steps=(step,)))

    assert items_for(the_plan, planner.DROP_DIR) == []


def test_a_family_with_a_single_revision_keeps_it():
    step = prune(name="playwright", run=(), keep_newest=KeepNewest(root=PLAYWRIGHT, keep=1))
    state = healthy(
        marks=(),
        versions=(CacheVersion(PLAYWRIGHT, "ffmpeg", (1011,), f"{PLAYWRIGHT}/ffmpeg-1011"),),
    )

    the_plan = planner.plan(state, desired(steps=(step,)))

    assert items_for(the_plan, planner.DROP_DIR) == []


def test_a_sweep_only_looks_at_the_cache_it_declared():
    step = prune(name="playwright", run=(), keep_newest=KeepNewest(root=PLAYWRIGHT, keep=1))
    state = healthy(
        marks=(),
        versions=(
            CacheVersion(PUPPETEER, "chrome/linux", (148,), f"{PUPPETEER}/a"),
            CacheVersion(PUPPETEER, "chrome/linux", (127,), f"{PUPPETEER}/b"),
        ),
    )

    the_plan = planner.plan(state, desired(steps=(step,)))

    assert items_for(the_plan, planner.DROP_DIR) == []


def test_leftover_install_archives_are_dropped_by_shape_and_not_by_age():
    step = prune(
        name="puppeteer-zips",
        run=(),
        drop_matching=DropMatching(root=PUPPETEER, suffix=".zip"),
    )
    state = healthy(
        marks=(),
        leftovers=(LeftoverFile(PUPPETEER, f"{PUPPETEER}/chrome/127-linux64.zip", 200 * 10**6),),
    )

    the_plan = planner.plan(state, desired(steps=(step,)))

    assert targets_for(the_plan, planner.DROP_FILE) == [f"{PUPPETEER}/chrome/127-linux64.zip"]


def test_a_sweep_with_nothing_obsolete_produces_no_item():
    step = prune(name="playwright", run=(), keep_newest=KeepNewest(root=PLAYWRIGHT, keep=1))

    the_plan = planner.plan(healthy(marks=()), desired(steps=(step,)))

    assert the_plan == Plan()


# --- a ordem permanente: o plano do ramo parado, emitido de véspera ------------


def test_the_standing_order_is_the_stopped_branch_plan_issued_while_the_wsl_is_up():
    """O ramo parado só é executável quando o planner é inalcançável, por construção.

    Entrar no WSL para planejar seria ligá-lo, que é a única coisa que este
    desenho promete nunca fazer. A ordem sai de véspera, do mesmo planner.
    """
    order = planner.standing_order(healthy(marks=()), desired())

    assert targets_for(order, planner.RUN_ON_HOST) == ["compact-vhdx"]


def test_the_standing_order_respects_the_cadence_of_the_stopped_branch():
    state = healthy(marks=(Mark(step="compact-vhdx", at=days_ago(2)),))

    order = planner.standing_order(state, desired())

    assert order == Plan()


def test_the_standing_order_carries_no_alarm_because_the_live_plan_already_did():
    state = healthy(
        marks=(),
        host=HostDisk(measured=True, free_bytes=GIGA, total_bytes=490 * GIGA),
    )

    order = planner.standing_order(state, desired())

    assert items_for(order, planner.NOTIFY) == []


def test_a_stopped_wsl_issues_no_standing_order_because_it_is_already_the_branch():
    order = planner.standing_order(healthy(wsl_running=False, marks=()), desired())

    assert order == Plan()


# --- nada é planejado para uma dimensão não decidida --------------------------


def test_an_undecided_step_list_plans_nothing():
    the_plan = planner.plan(healthy(marks=()), Desired())

    assert the_plan == Plan()


def test_an_undecided_floor_plans_no_disk_alarm_even_with_an_empty_disk():
    state = healthy(host=HostDisk(measured=True, free_bytes=0, total_bytes=490 * GIGA))

    the_plan = planner.plan(state, Desired(steps=()))

    assert the_plan == Plan()
