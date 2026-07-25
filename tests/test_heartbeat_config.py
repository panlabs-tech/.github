"""A configuração desejada do heartbeat, e o que ela recusa.

Metade destes testes é sobre o dado **entregue**: é ali que moram as decisões que
a issue cobra em critério de aceitação (o que a poda cobre, o que ela não faz, que
a tarefa nunca desliga nada). A outra metade é sobre o que a leitura recusa, e cada
recusa corresponde a um erro que só apareceria tarde: no host, elevado, ou num
alarme que saiu no canal errado.
"""

import json
from pathlib import Path

import pytest

from panlabs.checker.cli import EXIT_DRIFT, EXIT_ERROR
from panlabs.heartbeat.config import DEFAULT_CONFIG_PATH, Desired, load_desired
from panlabs.heartbeat.model import BRANCH_DOWN, BRANCH_UP

NEVER = ("--shutdown", "--terminate", "-t")
"""O que nenhum comando deste heartbeat pode conter, em nenhum ramo.

Desligar o WSL mataria sessão de trabalho no meio, e há repositórios com trabalho
não commitado morando lá dentro. O ciclo completo forçado foi rejeitado por isso.
"""


@pytest.fixture
def shipped() -> Desired:
    return load_desired(DEFAULT_CONFIG_PATH)


def shipped_step(shipped: Desired, name: str):
    """O passo entregue com este nome. Ele existir é parte do que se afirma."""
    found = [step for step in shipped.steps or () if step.name == name]
    assert found, f"o passo `{name}` não está declarado no dado entregue"
    return found[0]


def config_with(tmp_path: Path, **overrides: object) -> Path:
    base: dict[str, object] = {
        "channels": [{"name": "falha", "why": "um passo falhou"}],
        "host_floor": {"free_bytes": 25000000000, "alarm": "falha", "why": "piso"},
        "stale_mark": {"after_days": 3, "alarm": "falha", "why": "marca"},
        "unobserved": {"alarm": "falha", "why": "não observado"},
        "steps": [
            {
                "name": "npm",
                "branch": BRANCH_UP,
                "every_days": 7,
                "alarm": "falha",
                "why": "cache",
                "run": ["~/.local/bin/npm", "cache", "verify"],
            }
        ],
    }
    base.update(overrides)
    path = tmp_path / "heartbeat.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return path


# --- o dado entregue: é nele que os critérios de aceitação moram --------------


def test_the_shipped_configuration_is_fully_decided(shipped: Desired):
    assert shipped.undecided == ()


def test_the_shipped_pruning_covers_native_cleanup_browsers_and_leftovers(shipped: Desired):
    """O critério: comandos nativos, versão obsoleta de browser e arquivo órfão."""
    steps = shipped.steps or ()

    assert [s.name for s in steps if s.run] == [
        "npm-cache",
        "pnpm-store",
        "uv-cache",
        "pip-cache",
    ]
    assert [s.name for s in steps if s.keep_newest] == [
        "playwright-browsers",
        "puppeteer-browsers",
    ]
    assert [s.name for s in steps if s.drop_matching] == ["puppeteer-archives"]


def test_no_shipped_step_is_a_generic_age_sweep(shipped: Desired):
    """Rejeitada por mérito: ela erraria os dois maiores e apagaria o browser atual.

    A prova é estrutural e não textual: não existe corpo de passo que selecione por
    idade. Um passo só remove o que tem revisão mais nova, ou o que tem a forma de
    nome declarada.
    """
    for step in shipped.steps or ():
        assert step.run or step.keep_newest or step.drop_matching or step.on_host or step.report, (
            step.name
        )


def test_no_shipped_command_can_shut_the_wsl_down(shipped: Desired):
    for step in shipped.steps or ():
        command = step.run or (step.report.command if step.report else ())
        assert not set(command) & set(NEVER), step.name


# --- o passo que relata: código de saída vira canal ---------------------------


def test_the_shipped_configuration_declares_a_fourth_channel_with_its_reason(shipped: Desired):
    """Quarto canal, declarado como os outros três: deriva de anatomia é natureza própria."""
    channels = {channel.name: channel.why for channel in shipped.channels or ()}

    assert len(channels) == 4
    assert channels["anatomia"]


def test_the_shipped_checker_is_a_step_of_the_branch_where_the_wsl_is_up(shipped: Desired):
    """Ele precisa de rede e de token autenticado, e a poda não precisa de nada disso."""
    step = shipped_step(shipped, "anatomy-checker")

    assert step.branch == BRANCH_UP
    assert step.every_days >= 1


def test_the_shipped_checker_sends_drift_and_mechanism_failure_to_different_channels(
    shipped: Desired,
):
    """O critério inteiro do passo: token expirado não pode chegar como deriva.

    Os códigos são contrato com `panlabs.checker.cli`, e este teste amarra os dois
    lados: mudar o número lá sem mudar o mapa aqui mandaria o alarme para o canal
    errado, calado.
    """
    report = shipped_step(shipped, "anatomy-checker").report

    assert report is not None
    assert report.codes == {EXIT_DRIFT: "anatomia", EXIT_ERROR: "falha"}


def test_the_shipped_checker_alarms_on_the_mechanism_channel_when_it_cannot_even_run(
    shipped: Desired,
):
    """Um código não declarado é falha do passo, e o canal dele não é o da anatomia."""
    step = shipped_step(shipped, "anatomy-checker")

    assert step.alarm == "falha"


def test_the_stopped_branch_is_only_ever_the_compaction_and_it_is_the_hosts(
    shipped: Desired,
):
    down = [step for step in shipped.steps or () if step.branch == BRANCH_DOWN]

    assert [step.name for step in down] == ["compact-vhdx"]
    assert all(step.on_host for step in down)


def test_the_cheap_prunes_run_weekly_and_the_real_wipe_waits_a_month(shipped: Desired):
    """Disparo diário não é cadência da ação, e o dado entregue prova a diferença."""
    cadence = {step.name: step.every_days for step in shipped.steps or ()}

    assert cadence["npm-cache"] == 7
    assert cadence["pip-cache"] == 30
    assert cadence["compact-vhdx"] == 30


def test_every_shipped_executable_is_reachable_without_a_shell(shipped: Desired):
    """O passo roda em subprocesso sem rc, onde `~/.local/bin` não está no PATH."""
    for step in shipped.steps or ():
        command = step.run or (step.report.command if step.report else ())
        if command:
            assert command[0].startswith("/"), step.name


def test_the_shipped_floor_is_the_measured_one(shipped: Desired):
    assert shipped.host_floor is not None
    assert shipped.host_floor.free_bytes == 25_000_000_000


# --- o que a leitura recusa ---------------------------------------------------


def test_an_unknown_key_is_refused_instead_of_ignored(tmp_path: Path):
    path = tmp_path / "h.json"
    path.write_text(json.dumps({"passos": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="chave desconhecida"):
        load_desired(path)


def test_a_step_naming_an_undeclared_alarm_channel_is_refused(tmp_path: Path):
    """O alarme sairia no canal errado, que é o defeito que o desenho existe para evitar."""
    path = config_with(
        tmp_path,
        steps=[
            {
                "name": "checker",
                "branch": BRANCH_UP,
                "every_days": 1,
                "alarm": "conformidade",
                "why": "deriva",
                "run": ["/usr/bin/true"],
            }
        ],
    )

    with pytest.raises(ValueError, match="canal de alarme não declarado"):
        load_desired(path)


def report_step(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "checker",
        "branch": BRANCH_UP,
        "every_days": 1,
        "alarm": "falha",
        "why": "deriva de anatomia é alarme, não gate de PR",
        "report": {"command": ["/usr/bin/true"], "codes": {"1": "falha"}},
    }
    base.update(overrides)
    return base


def test_a_report_step_declares_which_channel_each_exit_code_speaks_on(tmp_path: Path):
    desired = load_desired(config_with(tmp_path, steps=[report_step()]))
    assert desired.steps is not None
    report = desired.steps[0].report

    assert report is not None
    assert report.codes == {1: "falha"}


def test_a_report_step_mapping_a_code_to_an_undeclared_channel_is_refused(tmp_path: Path):
    """O alarme sairia num canal que ninguém declarou, que é falhar calado no pior lugar."""
    path = config_with(
        tmp_path,
        steps=[report_step(report={"command": ["/usr/bin/true"], "codes": {"1": "anatomia"}})],
    )

    with pytest.raises(ValueError, match="canal de alarme não declarado"):
        load_desired(path)


def test_a_report_step_mapping_the_success_code_is_refused(tmp_path: Path):
    """Zero é o silêncio de um passo saudável, e alarmar nele treina o operador a ignorar."""
    path = config_with(
        tmp_path,
        steps=[report_step(report={"command": ["/usr/bin/true"], "codes": {"0": "falha"}})],
    )

    with pytest.raises(ValueError, match="código 0"):
        load_desired(path)


def test_a_report_step_with_no_code_mapped_is_refused(tmp_path: Path):
    """Sem mapa, todo código não-zero viraria falha genérica: o corpo não teria razão de ser."""
    path = config_with(
        tmp_path, steps=[report_step(report={"command": ["/usr/bin/true"], "codes": {}})]
    )

    with pytest.raises(ValueError, match="codes"):
        load_desired(path)


def test_a_report_step_with_a_non_numeric_exit_code_is_refused(tmp_path: Path):
    path = config_with(
        tmp_path,
        steps=[report_step(report={"command": ["/usr/bin/true"], "codes": {"deriva": "falha"}})],
    )

    with pytest.raises(ValueError, match="código de saída"):
        load_desired(path)


def test_a_report_step_with_no_command_is_refused(tmp_path: Path):
    path = config_with(tmp_path, steps=[report_step(report={"codes": {"1": "falha"}})])

    with pytest.raises(ValueError, match="command"):
        load_desired(path)


def test_the_report_executable_is_expanded_like_the_one_of_a_run_step(tmp_path: Path):
    path = config_with(
        tmp_path,
        steps=[
            report_step(
                report={
                    "command": ["~/.venv/bin/panlabs-checker", "--org"],
                    "codes": {"1": "falha"},
                }
            )
        ],
    )

    desired = load_desired(path)
    assert desired.steps is not None
    report = desired.steps[0].report

    assert report is not None
    assert report.command[0] == str(Path("~/.venv/bin/panlabs-checker").expanduser())
    assert report.command[1] == "--org"


def test_a_step_with_two_bodies_is_refused(tmp_path: Path):
    path = config_with(
        tmp_path,
        steps=[
            {
                "name": "npm",
                "branch": BRANCH_UP,
                "every_days": 7,
                "alarm": "falha",
                "why": "cache",
                "run": ["/usr/bin/true"],
                "drop_matching": {"root": "~/.cache/x", "suffix": ".zip"},
            }
        ],
    )

    with pytest.raises(ValueError, match="exatamente um corpo"):
        load_desired(path)


def test_a_step_with_no_body_is_refused(tmp_path: Path):
    path = config_with(
        tmp_path,
        steps=[
            {
                "name": "npm",
                "branch": BRANCH_UP,
                "every_days": 7,
                "alarm": "falha",
                "why": "cache",
            }
        ],
    )

    with pytest.raises(ValueError, match="exatamente um corpo"):
        load_desired(path)


def test_a_stopped_branch_step_that_runs_inside_the_wsl_is_refused(tmp_path: Path):
    """Realizá-lo exigiria ligar o WSL, que é a única coisa que o desenho nunca faz."""
    path = config_with(
        tmp_path,
        steps=[
            {
                "name": "compact",
                "branch": BRANCH_DOWN,
                "every_days": 30,
                "alarm": "falha",
                "why": "compacta",
                "run": ["/usr/bin/true"],
            }
        ],
    )

    with pytest.raises(ValueError, match="não declara `on_host`"):
        load_desired(path)


def test_a_host_step_on_the_running_branch_is_refused(tmp_path: Path):
    """Ele ficaria planejado e nunca executado: o applier de dentro não age no host."""
    path = config_with(
        tmp_path,
        steps=[
            {
                "name": "compact",
                "branch": BRANCH_UP,
                "every_days": 30,
                "alarm": "falha",
                "why": "compacta",
                "on_host": True,
            }
        ],
    )

    with pytest.raises(ValueError, match="fora do ramo"):
        load_desired(path)


def test_an_unknown_branch_is_refused(tmp_path: Path):
    path = config_with(
        tmp_path,
        steps=[
            {
                "name": "npm",
                "branch": "quando-der",
                "every_days": 7,
                "alarm": "falha",
                "why": "cache",
                "run": ["/usr/bin/true"],
            }
        ],
    )

    with pytest.raises(ValueError, match="ramo desconhecido"):
        load_desired(path)


def test_two_steps_with_the_same_name_are_refused(tmp_path: Path):
    """O nome é a chave da marca, e dois passos homônimos dividiriam cadência."""
    step = {
        "name": "npm",
        "branch": BRANCH_UP,
        "every_days": 7,
        "alarm": "falha",
        "why": "cache",
        "run": ["/usr/bin/true"],
    }
    path = config_with(tmp_path, steps=[step, dict(step)])

    with pytest.raises(ValueError, match="passo repetido"):
        load_desired(path)


# --- a expansão de caminho ----------------------------------------------------


def test_the_executable_of_a_step_is_expanded_and_its_arguments_are_not(tmp_path: Path):
    desired = load_desired(config_with(tmp_path))
    assert desired.steps is not None
    step = desired.steps[0]

    assert step.run[0] == str(Path("~/.local/bin/npm").expanduser())
    assert step.run[1:] == ("cache", "verify")


def test_a_sweep_root_is_expanded(tmp_path: Path):
    path = config_with(
        tmp_path,
        steps=[
            {
                "name": "playwright",
                "branch": BRANCH_UP,
                "every_days": 7,
                "alarm": "falha",
                "why": "browser",
                "keep_newest": {"root": "~/.cache/ms-playwright"},
            }
        ],
    )

    desired = load_desired(path)
    assert desired.steps is not None
    keep = desired.steps[0].keep_newest

    assert keep is not None
    assert keep.root == str(Path("~/.cache/ms-playwright").expanduser())


# --- não decidido não é decidido como vazio -----------------------------------


def test_an_absent_dimension_is_undecided_and_not_an_empty_decision(tmp_path: Path):
    path = tmp_path / "h.json"
    path.write_text(json.dumps({"steps": []}), encoding="utf-8")

    desired = load_desired(path)

    assert desired.steps == ()
    assert "channels" in desired.undecided
    assert "steps" not in desired.undecided
