"""A interface do script de máquina: plano por default, e nada além disso.

Aqui plano por default deixa de ser conveniência e vira requisito de segurança:
este é o único script do repo que **apaga diretório**. O teste que mais importa é
o negativo -- rodar sem argumento não pode encostar em nada.
"""

import json
from pathlib import Path

import pytest

from panlabs.machine import applier
from panlabs.machine.cli import main


@pytest.fixture
def forbid_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum efeito pode rodar sem `--apply`. Um só já seria um bug grave."""

    def explode(_item: object) -> None:
        raise AssertionError("o script de máquina agiu sem --apply")

    monkeypatch.setattr(applier, "EFFECTS", dict.fromkeys(applier.EFFECTS, explode))


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
