"""A interface do script de máquina: plano por default, e nada além disso.

Aqui plano por default deixa de ser conveniência e vira requisito de segurança:
este é o único script do repo que **apaga diretório**. O teste que mais importa é
o negativo -- rodar sem argumento não pode encostar em nada.
"""

import json
from pathlib import Path

import pytest

from panlabs.machine import applier, planner
from panlabs.machine.cli import main
from panlabs.plan import PlanItem


@pytest.fixture
def forbid_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum efeito pode rodar sem `--apply`. Um só já seria um bug grave."""

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("o script de máquina agiu sem --apply")

    monkeypatch.setattr(applier, "build_effects", explode)


def snapshot(tmp_path: Path, **overrides: object) -> Path:
    raw: dict[str, object] = {
        "links": [{"name": "fd", "points_to": "", "resolved": ""}],
        "retire": [{"path": "/gone", "present": True, "bytes": 900_000_000}],
        "credentials": [
            {
                "path": "/home/op/.aws",
                "present": True,
                "resolved": "/mnt/c/Users/op/.aws",
                "is_dir": True,
                "entries": 4,
            }
        ],
        "denylist": [],
        "statusline": "npx ccstatusline@latest",
        "global_skills": [],
        "vendored_skills": [],
    }
    raw.update(overrides)
    path = tmp_path / "observed.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def config(tmp_path: Path) -> Path:
    path = tmp_path / "machine.json"
    path.write_text(
        json.dumps(
            {
                "bin_dir": "/home/op/.local/bin",
                "links": [{"name": "fd", "target": "/usr/bin/fdfind", "why": "subprocesso"}],
                "retire": [{"path": "/gone", "why": "fantasma"}],
                "read_denylist": [{"path": "/home/op/.aws", "why": "chave de 2022"}],
                "statusline": "/home/op/.local/bin/ccstatusline",
                "skills": {},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_running_without_a_flag_changes_nothing(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = main(["--config", str(config(tmp_path)), "--observed", str(snapshot(tmp_path))])

    assert code == 0
    assert "link-name" in capsys.readouterr().out


def test_applying_from_a_saved_snapshot_is_refused(tmp_path: Path):
    """O retrato pode estar velho, e aqui agir sobre estado velho apaga diretório."""
    code = main(
        ["--config", str(config(tmp_path)), "--observed", str(snapshot(tmp_path)), "--apply"]
    )

    assert code == 2


def test_the_plan_the_operator_reads_carries_action_target_and_reason(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    main(["--config", str(config(tmp_path)), "--observed", str(snapshot(tmp_path))])

    out = capsys.readouterr().out
    assert "/home/op/.local/bin/fd" in out
    assert "subprocesso" in out
    # A negação aparece sobre o alvo resolvido, não sobre o nome escrito.
    assert "/mnt/c/Users/op/.aws" in out


def test_an_undecided_dimension_is_reported_instead_of_passing_silently(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps({"bin_dir": "/home/op/.local/bin"}), encoding="utf-8")

    main(["--config", str(partial), "--observed", str(snapshot(tmp_path))])

    err = capsys.readouterr().err
    assert "ainda sem decisão" in err


def test_a_broken_config_is_an_error_and_not_an_empty_plan(tmp_path: Path):
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"links": [{"name": "fd"}]}), encoding="utf-8")

    code = main(["--config", str(broken), "--observed", str(snapshot(tmp_path))])

    assert code == 1


def test_the_summary_reports_the_real_radius_and_not_the_declared_list(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Diretório suspeito e vazio não conta como credencial no resumo."""
    observed = snapshot(
        tmp_path,
        credentials=[
            {
                "path": "/home/op/.aws",
                "present": True,
                "resolved": "/mnt/c/Users/op/.aws",
                "is_dir": True,
                "entries": 4,
            },
            {
                "path": "/home/op/secrets",
                "present": True,
                "resolved": "/home/op/secrets",
                "is_dir": True,
                "entries": 0,
            },
        ],
    )

    main(["--config", str(config(tmp_path)), "--observed", str(observed)])

    assert "1 lugar(es) de credencial com conteúdo hoje" in capsys.readouterr().out


def test_the_summary_does_not_count_a_name_that_exists_and_does_not_run(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """O resumo declarava alcançável um nome morto, porque contava presença.

    Foi assim que a barra de status ficou quebrada sem ninguém ver: o link
    existia e apontava para onde o dado pedia.
    """
    observed = snapshot(
        tmp_path,
        links=[
            {
                "name": "ccstatusline",
                "points_to": "/home/op/pkg/.bin/ccstatusline",
                "resolved": "/home/op/pkg/.bin/ccstatusline",
                "anchored_target": True,
            }
        ],
    )

    main(["--config", str(config(tmp_path)), "--observed", str(observed)])

    out = capsys.readouterr().out
    assert "0/1 nome(s) alcançável(is)" in out
    assert "faltam: ccstatusline" in out


# --- a fronteira entre o que tem efeito e o que é manual ----------------------


def test_every_action_the_planner_emits_is_either_manual_or_has_an_effect():
    """A tabela de despacho não pode divergir do vocabulário de ações.

    Uma ação nova sem efeito e fora de MANUAL_ACTIONS estouraria com KeyError na
    hora de aplicar, e uma ação manual **com** efeito registrado realizaria o ato
    que a fronteira entre as specs proíbe aqui. Este teste fecha os dois lados.
    """
    effects = applier.build_effects(settings=Path("/nowhere/settings.json"))
    emitted = {
        planner.LINK_NAME,
        planner.RETIRE_DIR,
        planner.DENY_READ,
        planner.PIN_STATUSLINE,
        planner.PROMOTE_SKILL,
        planner.DISCARD_SKILL,
        planner.DROP_VENDORED_SKILL,
        planner.UNREACHABLE_NAME,
    }

    assert set(effects) == emitted - set(planner.MANUAL_ACTIONS)


def test_installing_a_skill_has_no_effect_because_the_cli_is_the_only_mechanism():
    effects = applier.build_effects(settings=Path("/nowhere/settings.json"))

    assert planner.PROMOTE_SKILL not in effects


def test_the_denial_is_written_to_the_settings_file_it_was_given(tmp_path: Path):
    """Observar um arquivo e escrever em outro seria o applier decidindo o alvo."""
    settings = tmp_path / "elsewhere.json"
    settings.write_text(json.dumps({"model": "keep-me"}), encoding="utf-8")

    effects = applier.build_effects(settings=settings)
    effects[planner.DENY_READ](
        PlanItem(
            action=planner.DENY_READ,
            target="/mnt/c/Users/op/.aws",
            reason="chave de 2022",
            payload={"entry": "Read(//mnt/c/Users/op/.aws/**)"},
        )
    )

    written = json.loads(settings.read_text(encoding="utf-8"))
    assert written["permissions"]["deny"] == ["Read(//mnt/c/Users/op/.aws/**)"]
    # Ele é dono de duas chaves, não do arquivo.
    assert written["model"] == "keep-me"


def test_denying_the_same_path_twice_does_not_duplicate_the_entry(tmp_path: Path):
    settings = tmp_path / "s.json"
    item = PlanItem(
        action=planner.DENY_READ,
        target="/x",
        reason="r",
        payload={"entry": "Read(//x/**)"},
    )

    effects = applier.build_effects(settings=settings)
    effects[planner.DENY_READ](item)
    effects[planner.DENY_READ](item)

    written = json.loads(settings.read_text(encoding="utf-8"))
    assert written["permissions"]["deny"] == ["Read(//x/**)"]
