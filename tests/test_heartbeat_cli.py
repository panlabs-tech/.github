"""A interface do heartbeat, e os efeitos que ela dispara.

Plano por default vale aqui pelo mesmo motivo do script de máquina, e por um a
mais: este script **apaga diretório** e, pelo ramo parado, dirige uma ferramenta
elevada do host contra um disco virtual. Rodar sem argumento não pode encostar em
nada.

O `apply` é fino por construção, mas três comportamentos dele são decisão escrita
e por isso têm teste: a marca da própria execução ser gravada mesmo com o plano
vazio, a falha de um passo sair no canal **dele**, e a falha de um passo não
interromper os outros.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from panlabs.heartbeat import applier, planner
from panlabs.heartbeat.applier import build_runner, write_standing_order
from panlabs.heartbeat.cli import main
from panlabs.heartbeat.model import BRANCH_DOWN, BRANCH_UP
from panlabs.plan import Plan, PlanItem, apply

NOW = datetime(2026, 7, 25, 3, 0, tzinfo=UTC)
GIGA = 1_000_000_000


@pytest.fixture
def forbid_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum efeito pode rodar sem `--apply`. Um só já seria um bug grave."""

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("o heartbeat agiu sem --apply")

    monkeypatch.setattr(applier, "build_runner", explode)
    monkeypatch.setattr(applier, "run_command", explode)


def snapshot(tmp_path: Path, **overrides: object) -> Path:
    raw: dict[str, object] = {
        "now": NOW.isoformat(),
        "wsl_running": True,
        "host": {"measured": True, "free_bytes": 20 * GIGA, "total_bytes": 490 * GIGA},
        "last_run": "2026-07-24T03:00:00+00:00",
        "marks": [],
        "versions": [],
        "leftovers": [],
    }
    raw.update(overrides)
    path = tmp_path / "observed.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def config(tmp_path: Path) -> Path:
    path = tmp_path / "heartbeat.json"
    path.write_text(
        json.dumps(
            {
                "channels": [
                    {"name": "falha", "why": "um passo falhou"},
                    {"name": "disco", "why": "o host cruzou o piso"},
                    {"name": "marca", "why": "a tarefa parou"},
                ],
                "host_floor": {"free_bytes": 25 * GIGA, "alarm": "disco", "why": "2 meses"},
                "stale_mark": {"after_days": 3, "alarm": "marca", "why": "disparo diário"},
                "unobserved": {"alarm": "falha", "why": "não observado é falha"},
                "steps": [
                    {
                        "name": "npm-cache",
                        "branch": BRANCH_UP,
                        "every_days": 7,
                        "alarm": "falha",
                        "why": "3,6 GB fora de ~/.cache",
                        "run": ["/usr/bin/true", "cache", "verify"],
                    },
                    {
                        "name": "compact-vhdx",
                        "branch": BRANCH_DOWN,
                        "every_days": 30,
                        "alarm": "falha",
                        "why": "o único caminho nesta edição do Windows",
                        "on_host": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


# --- plano por default --------------------------------------------------------


def test_running_without_a_flag_changes_nothing(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = main(["--config", str(config(tmp_path)), "--observed", str(snapshot(tmp_path))])

    assert code == 0
    assert "run-step" in capsys.readouterr().out


def test_applying_from_a_saved_snapshot_is_refused(tmp_path: Path):
    """Um retrato velho pode dizer "parado" com o WSL de pé, e aí a compactação mata."""
    code = main(
        ["--config", str(config(tmp_path)), "--observed", str(snapshot(tmp_path)), "--apply"]
    )

    assert code == 2


def test_the_plan_the_operator_reads_carries_action_target_and_reason(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    main(["--config", str(config(tmp_path)), "--observed", str(snapshot(tmp_path))])

    out = capsys.readouterr().out
    assert "npm-cache" in out
    assert "3,6 GB fora de ~/.cache" in out
    # O alarme de disco aparece, e aparece antes do passo.
    assert out.index("disco do host") < out.index("npm-cache")


def test_an_undecided_dimension_is_reported_instead_of_passing_silently(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps({"steps": []}), encoding="utf-8")

    main(["--config", str(partial), "--observed", str(snapshot(tmp_path))])

    assert "ainda sem decisão" in capsys.readouterr().err


def test_a_broken_config_is_an_error_and_not_an_empty_plan(tmp_path: Path):
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"steps": [{"name": "x"}]}), encoding="utf-8")

    code = main(["--config", str(broken), "--observed", str(snapshot(tmp_path))])

    assert code == 1


def test_the_summary_says_the_host_disk_was_not_measured_instead_of_showing_a_zero(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    observed = snapshot(tmp_path, host={"measured": False, "free_bytes": 0, "total_bytes": 0})

    main(["--config", str(config(tmp_path)), "--observed", str(observed)])

    assert "NÃO medido" in capsys.readouterr().out


# --- a fronteira entre o que tem efeito aqui e o que é ato do host ------------


def test_every_action_the_planner_emits_is_either_the_hosts_or_has_an_effect(tmp_path: Path):
    """A tabela de despacho não pode divergir do vocabulário de ações.

    Uma ação nova sem efeito e fora de `HOST_ACTIONS` estouraria com KeyError na
    hora de aplicar, e uma ação do host **com** efeito registrado aqui realizaria
    de dentro do WSL um ato que só existe com o WSL parado.
    """
    runner = build_runner(state_dir=tmp_path, now=NOW)
    emitted = {
        planner.RUN_STEP,
        planner.DROP_DIR,
        planner.DROP_FILE,
        planner.RUN_ON_HOST,
        planner.NOTIFY,
    }

    assert set(runner.effects) == emitted - set(planner.HOST_ACTIONS)


def test_the_compaction_has_no_effect_on_this_side_of_the_boundary(tmp_path: Path):
    runner = build_runner(state_dir=tmp_path, now=NOW)

    assert planner.RUN_ON_HOST not in runner.effects


# --- o que o apply grava ------------------------------------------------------


def item(action: str, target: str, **payload: object) -> PlanItem:
    return PlanItem(action=action, target=target, reason="porque sim", payload=payload)


def test_the_run_mark_is_written_even_when_the_plan_is_empty(tmp_path: Path):
    """É essa marca que o vigia de homem-morto lê no startup do shell.

    Uma máquina saudável que não escrevesse marca ficaria indistinguível de uma
    tarefa que um update do Windows desabilitou, que é o cenário exato que o vigia
    existe para pegar.
    """
    runner = build_runner(state_dir=tmp_path, now=NOW)

    apply(Plan(), runner.effects)
    runner.commit()

    marks = json.loads((tmp_path / "marks.json").read_text(encoding="utf-8"))
    assert marks["last_run"] == NOW.isoformat()


def test_a_step_that_succeeded_stamps_its_own_mark(tmp_path: Path):
    runner = build_runner(state_dir=tmp_path, now=NOW, run=lambda _c: (0, ""))

    apply(
        Plan((item(planner.RUN_STEP, "npm-cache", step="npm-cache", run=["x"], alarm="falha"),)),
        runner.effects,
    )
    runner.commit()

    marks = json.loads((tmp_path / "marks.json").read_text(encoding="utf-8"))
    assert marks["steps"] == {"npm-cache": NOW.isoformat()}


def test_a_step_that_failed_does_not_stamp_its_mark(tmp_path: Path):
    """Marcar um passo que falhou lhe daria mais uma semana de folga a cada tentativa."""
    runner = build_runner(state_dir=tmp_path, now=NOW, run=lambda _c: (1, "sem rede"))

    apply(
        Plan((item(planner.RUN_STEP, "npm-cache", step="npm-cache", run=["x"], alarm="falha"),)),
        runner.effects,
    )
    runner.commit()

    marks = json.loads((tmp_path / "marks.json").read_text(encoding="utf-8"))
    assert marks["steps"] == {}


def test_a_failing_step_alarms_on_its_own_channel_and_not_on_the_disk_one(tmp_path: Path):
    """Falha de rede num passo não pode se disfarçar de alarme de disco."""
    runner = build_runner(state_dir=tmp_path, now=NOW, run=lambda _c: (1, "token expirado"))

    apply(
        Plan(
            (
                item(planner.RUN_STEP, "checker", step="checker", run=["x"], alarm="conformidade"),
                item(planner.NOTIFY, "disco do host", alarm="disco", message="abaixo do piso"),
            )
        ),
        runner.effects,
    )

    assert [alarm.alarm for alarm in runner.alarms] == ["conformidade", "disco"]


def test_a_failing_step_does_not_stop_the_ones_after_it(tmp_path: Path):
    """Três passos independentes não são uma corrente."""
    runner = build_runner(state_dir=tmp_path, now=NOW, run=lambda c: (0 if "ok" in c else 1, ""))

    apply(
        Plan(
            (
                item(planner.RUN_STEP, "quebra", step="quebra", run=["nope"], alarm="falha"),
                item(planner.RUN_STEP, "segue", step="segue", run=["ok"], alarm="falha"),
            )
        ),
        runner.effects,
    )
    runner.commit()

    assert runner.failed == ["quebra"]
    marks = json.loads((tmp_path / "marks.json").read_text(encoding="utf-8"))
    assert marks["steps"] == {"segue": NOW.isoformat()}


def test_a_healthy_run_writes_an_empty_alarm_file_instead_of_keeping_the_old_one(
    tmp_path: Path,
):
    """Silencioso quando saudável, e é assim que "silencioso" fica escrito em disco."""
    (tmp_path).mkdir(parents=True, exist_ok=True)
    (tmp_path / "alarms.json").write_text(
        json.dumps([{"alarm": "disco", "message": "da semana passada"}]), encoding="utf-8"
    )
    runner = build_runner(state_dir=tmp_path, now=NOW)

    apply(Plan(), runner.effects)
    runner.commit()

    assert json.loads((tmp_path / "alarms.json").read_text(encoding="utf-8")) == []


def test_an_obsolete_directory_is_removed_and_the_step_is_stamped(tmp_path: Path):
    doomed = tmp_path / "chromium-1161"
    doomed.mkdir()
    (doomed / "chrome").write_text("x", encoding="utf-8")
    runner = build_runner(state_dir=tmp_path / "state", now=NOW)

    apply(
        Plan(
            (
                item(
                    planner.DROP_DIR,
                    str(doomed),
                    step="playwright",
                    path=str(doomed),
                    alarm="falha",
                ),
            )
        ),
        runner.effects,
    )

    assert not doomed.exists()
    assert runner.stamped == {"playwright"}


# --- a ordem permanente -------------------------------------------------------


def test_the_standing_order_is_left_where_the_host_will_find_it(tmp_path: Path):
    order = Plan((item(planner.RUN_ON_HOST, "compact-vhdx", step="compact-vhdx", alarm="falha"),))

    write_standing_order(order, tmp_path)

    written = json.loads((tmp_path / "standing-order.json").read_text(encoding="utf-8"))
    assert [entry["target"] for entry in written["items"]] == ["compact-vhdx"]


def test_an_order_that_is_no_longer_due_is_removed_instead_of_left_behind(tmp_path: Path):
    """Sem isso o host precisaria julgar idade, e a cadência viveria em dois lugares."""
    (tmp_path / "standing-order.json").write_text("{}", encoding="utf-8")

    write_standing_order(Plan(), tmp_path)

    assert not (tmp_path / "standing-order.json").exists()
