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


def observe_link(tmp_path: Path, bin_dir: Path) -> dict[str, object]:
    raw = fetch_raw(
        Desired(bin_dir=str(bin_dir), links=(DesiredLink(name="tool", target="x", why="y"),)),
        settings=tmp_path / "settings.json",
        global_skills=(tmp_path / "none",),
        workspaces=tmp_path / "workspaces",
    )
    (entry,) = raw["links"]
    return entry


SHIM_ANCHORED_ON_ITS_OWN_DIR = """#!/bin/sh
basedir=$(dirname "$0")
exec node "$basedir/../pkg/dist/tool.js" "$@"
"""
"""A forma exata do shim que quebrou a barra de status, reduzida ao essencial."""


def test_a_target_that_computes_what_to_run_from_its_own_dir_is_recorded_as_anchored(
    tmp_path: Path,
):
    """O defeito medido: alcançado pelo link, ele procura o pacote ao lado do link.

    Sem este campo o link passa na verificação, porque aponta exatamente para
    onde o dado pediu, e o nome continua morto para quem o invoca.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    real = tmp_path / "pkg-bin" / "tool"
    real.parent.mkdir()
    real.write_text(SHIM_ANCHORED_ON_ITS_OWN_DIR, encoding="utf-8")
    (bin_dir / "tool").symlink_to(real)

    assert observe_link(tmp_path, bin_dir)["anchored_target"] is True


def test_a_compiled_target_is_not_anchored_because_it_resolves_by_the_name_it_was_called_with(
    tmp_path: Path,
):
    """O shim do gerenciador de runtime é binário, e é por isso que ele sobrevive ao link."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    real = tmp_path / "shim"
    real.write_bytes(b"\x7fELF\x02\x01\x01\x00 not a script")
    (bin_dir / "tool").symlink_to(real)

    assert observe_link(tmp_path, bin_dir)["anchored_target"] is False


def test_a_script_that_never_leaves_its_own_dir_is_not_anchored(tmp_path: Path):
    """Ancorar só custa quando o shim compõe o próprio diretório com `..` para achar o pacote."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    real = tmp_path / "tool"
    real.write_text('#!/bin/sh\nexec echo "$@"\n', encoding="utf-8")
    (bin_dir / "tool").symlink_to(real)

    assert observe_link(tmp_path, bin_dir)["anchored_target"] is False


def test_a_name_that_is_not_a_link_is_never_anchored_because_nothing_moved_it(tmp_path: Path):
    """Um arquivo real no `bin_dir` roda no próprio diretório: o link é que quebra."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "tool").write_text(SHIM_ANCHORED_ON_ITS_OWN_DIR, encoding="utf-8")

    assert observe_link(tmp_path, bin_dir)["anchored_target"] is False


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


def test_an_org_repo_nested_under_the_org_mirror_dir_is_scanned(tmp_path: Path):
    """O layout que a issue #21 impõe põe todo repo da org um nível mais fundo.

    Varrer só um nível deixaria a cláusula de zero redundância cega exatamente na
    metade da frota que é da org, que é a metade que mais importa.
    """
    workspaces = tmp_path / "workspaces"
    skill(workspaces / "panlabs-tech" / ".github" / ".claude" / "skills", "tdd")
    skill(workspaces / "personal-repo" / ".claude" / "skills", "caveman")

    raw = fetch_raw(
        Desired(bin_dir=str(tmp_path / "bin")),
        settings=tmp_path / "settings.json",
        global_skills=(tmp_path / "none",),
        workspaces=workspaces,
    )

    found = sorted((e["repo"], e["name"]) for e in raw["vendored_skills"])
    assert found == [("panlabs-tech/.github", "tdd"), ("personal-repo", "caveman")]
