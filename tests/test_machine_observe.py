"""A observação da máquina: o que o disco diz, antes de qualquer decisão.

O teste que importa aqui é o de "onde uma skill global mora". A CLI de
distribuição escolhe entre dois diretórios globais, e uma medição que conheça só
um deles reporta como ausente uma skill que está instalada -- o que faria o plano
pedir a mesma promoção em toda rodada.
"""

from pathlib import Path

from panlabs.machine.config import Desired, DesiredLink, DesiredSecret
from panlabs.machine.observe import build_observed, fetch_raw


def skill(root: Path, name: str) -> None:
    (root / name).mkdir(parents=True, exist_ok=True)
    (root / name / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")


def test_a_skill_installed_in_either_global_dir_counts_as_global(tmp_path: Path):
    """A CLI instala num dos dois diretórios globais, e os dois valem."""
    agents = tmp_path / "agents" / "skills"
    claude = tmp_path / "claude" / "skills"
    skill(agents, "tdd")
    skill(claude, "caveman")

    raw = fetch_raw(
        Desired(bin_dir=str(tmp_path / "bin")),
        settings=tmp_path / "settings.json",
        global_skills=(agents, claude),
        workspaces=tmp_path / "workspaces",
    )

    assert sorted(raw["global_skills"]) == ["caveman", "tdd"]


def test_the_same_skill_in_both_global_dirs_is_reported_once(tmp_path: Path):
    agents = tmp_path / "agents" / "skills"
    claude = tmp_path / "claude" / "skills"
    skill(agents, "tdd")
    skill(claude, "tdd")

    raw = fetch_raw(
        Desired(bin_dir=str(tmp_path / "bin")),
        settings=tmp_path / "settings.json",
        global_skills=(agents, claude),
        workspaces=tmp_path / "workspaces",
    )

    assert raw["global_skills"] == ["tdd"]


def test_a_repo_whose_name_starts_with_a_dot_is_not_skipped_by_the_scan(tmp_path: Path):
    """O repo meta da org começa com ponto, e um glob ingênuo o perderia sempre."""
    workspaces = tmp_path / "workspaces"
    skill(workspaces / ".github" / ".claude" / "skills", "tdd")

    raw = fetch_raw(
        Desired(bin_dir=str(tmp_path / "bin")),
        settings=tmp_path / "settings.json",
        global_skills=(tmp_path / "none",),
        workspaces=workspaces,
    )

    assert [(e["repo"], e["name"]) for e in raw["vendored_skills"]] == [(".github", "tdd")]


def test_a_name_reached_through_a_symlink_records_the_immediate_target_and_the_end(tmp_path: Path):
    """Duas perguntas diferentes: para onde aponta, e onde mora de verdade."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    real = tmp_path / "real-tool"
    real.write_text("#!/bin/sh\n", encoding="utf-8")
    middle = tmp_path / "middle"
    middle.symlink_to(real)
    (bin_dir / "tool").symlink_to(middle)

    raw = fetch_raw(
        Desired(bin_dir=str(bin_dir), links=(DesiredLink(name="tool", target="x", why="y"),)),
        settings=tmp_path / "settings.json",
        global_skills=(tmp_path / "none",),
        workspaces=tmp_path / "workspaces",
    )

    (entry,) = raw["links"]
    assert entry["points_to"] == str(middle)
    assert entry["resolved"] == str(real)


def test_a_credential_dir_behind_a_symlink_records_the_resolved_target(tmp_path: Path):
    """É este campo que a negação usa, porque o shell fala com o alvo."""
    real = tmp_path / "windows-side" / ".aws"
    real.mkdir(parents=True)
    (real / "credentials").write_text("x\n", encoding="utf-8")
    link = tmp_path / ".aws"
    link.symlink_to(real)

    raw = fetch_raw(
        Desired(read_denylist=(DesiredSecret(path=str(link), why="chave"),)),
        settings=tmp_path / "settings.json",
        global_skills=(tmp_path / "none",),
        workspaces=tmp_path / "workspaces",
    )

    (entry,) = raw["credentials"]
    assert entry["resolved"] == str(real)
    assert entry["entries"] == 1
    assert build_observed(raw).credentials[0].is_linked
