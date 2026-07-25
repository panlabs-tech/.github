"""A interface do script de espaço de trabalho: plano por default, e nada além.

Aqui plano por default deixa de ser conveniência e vira requisito de segurança:
este script apaga diretório, reescreve remote e move repositório. Os testes que
mais importam são os negativos: rodar sem argumento não pode encostar em nada, e
nenhum descarte pode virar aplicável sem o operador nomear o alvo.
"""

import json
from pathlib import Path

import pytest

from panlabs.plan import PlanItem
from panlabs.workspace import applier, planner
from panlabs.workspace.cli import main

ORG = "panlabs-tech"
ROOT = "/home/op/workspaces"


@pytest.fixture
def forbid_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum efeito pode rodar sem `--apply`. Um só já seria um bug grave."""

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("o script de espaço de trabalho agiu sem --apply")

    monkeypatch.setattr(applier, "build_effects", explode)


def snapshot(tmp_path: Path, **overrides: object) -> Path:
    raw: dict[str, object] = {
        "org": ORG,
        "root": ROOT,
        "org_repos": ["skills"],
        "dirs": [
            {
                "path": f"{ROOT}/b3stocks",
                "kind": "repo",
                "remote": "https://github.com/ThiagoPanini/b3stocks.git",
                "head": "main",
                "branches": [{"name": "main", "content_on_remote": True, "commit_on_remote": True}],
            },
            {
                "path": f"{ROOT}/campfire",
                "kind": "repo",
                "remote": "https://github.com/ThiagoPanini/campfire.git",
                "head": "main",
                "dirty": ["rascunho/a.md"],
                "branches": [{"name": "main", "content_on_remote": True, "commit_on_remote": True}],
            },
        ],
    }
    raw.update(overrides)
    path = tmp_path / "observed.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def config(tmp_path: Path, **overrides: object) -> Path:
    body: dict[str, object] = {
        "root": ROOT,
        "remote": "https://github.com/{org}/{name}.git",
        "migrated_from": ["ThiagoPanini"],
        "worktrees": ".claude/worktrees",
    }
    body.update(overrides)
    path = tmp_path / "workspace.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def run(tmp_path: Path, *extra: str) -> int:
    return main(["--config", str(config(tmp_path)), "--observed", str(snapshot(tmp_path)), *extra])


def test_running_without_a_flag_changes_nothing(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = run(tmp_path)

    assert code == 0
    assert planner.CLONE_REPO in capsys.readouterr().out


def test_applying_from_a_saved_snapshot_is_refused(tmp_path: Path):
    """O retrato pode estar velho, e aqui agir sobre estado velho apaga diretório."""
    code = run(tmp_path, "--apply")

    assert code == 2


def test_the_plan_the_operator_reads_carries_action_target_and_reason(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    run(tmp_path)

    out = capsys.readouterr().out
    assert f"{ROOT}/{ORG}/skills" in out
    assert "não tem clone nesta máquina" in out
    assert "só existem neste disco" in out


def test_the_discard_of_an_eligible_dir_is_shown_and_held(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    run(tmp_path)

    out = capsys.readouterr().out
    assert planner.DISCARD_DIR in out
    assert "retido" in out


# --- o recorte de invocação ---------------------------------------------------


def test_only_keeps_the_named_subtree_and_nothing_else(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = run(tmp_path, "--only", f"{ROOT}/campfire", "--json")

    assert code == 0
    targets = {item["target"] for item in json.loads(capsys.readouterr().out)["items"]}
    assert targets == {f"{ROOT}/campfire"}


def test_only_takes_a_repository_together_with_what_lives_under_it(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """A subárvore é a unidade: um repositório vem com os worktrees dele."""
    code = run(tmp_path, "--only", ROOT, "--json")

    assert code == 0
    assert len(json.loads(capsys.readouterr().out)["items"]) > 1


def test_what_the_cut_left_out_is_reported_instead_of_vanishing(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Um plano recortado não é o plano do espaço, e ler um pelo outro seria caro."""
    run(tmp_path, "--only", f"{ROOT}/campfire")

    assert "continuam pendentes" in capsys.readouterr().err


def test_the_cut_never_changes_what_the_planner_decided(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Recortar o observado produziria um plano diferente; recortar o plano, não."""
    run(tmp_path, "--only", f"{ROOT}/campfire", "--json")
    cut = json.loads(capsys.readouterr().out)["items"]

    run(tmp_path, "--json")
    whole = [
        item
        for item in json.loads(capsys.readouterr().out)["items"]
        if item["target"] == f"{ROOT}/campfire"
    ]

    assert cut == whole


def test_naming_a_target_that_is_not_eligible_is_an_error_and_not_silence(tmp_path: Path):
    """Um caminho errado sairia como plano sem aquele descarte, que se lê como "não
    era elegível" quando na verdade foi erro de digitação."""
    code = run(tmp_path, "--discard", f"{ROOT}/nao-existe")

    assert code == 1


def test_naming_an_eligible_target_lifts_the_hold_on_that_target_alone(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = run(tmp_path, "--discard", f"{ROOT}/b3stocks", "--json")

    assert code == 0
    discards = {
        item["target"]: item["hold"]
        for item in json.loads(capsys.readouterr().out)["items"]
        if item["action"] == planner.DISCARD_DIR
    }
    assert discards == {f"{ROOT}/b3stocks": ""}


def test_an_undecided_dimension_is_reported_instead_of_passing_silently(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps({"root": ROOT}), encoding="utf-8")

    main(["--config", str(partial), "--observed", str(snapshot(tmp_path))])

    assert "ainda sem decisão" in capsys.readouterr().err


def test_a_broken_config_is_an_error_and_not_an_empty_plan(tmp_path: Path):
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"remote": "https://github.com/x/y.git"}), encoding="utf-8")

    code = main(["--config", str(broken), "--observed", str(snapshot(tmp_path))])

    assert code == 1


def test_the_summary_counts_what_carries_work_that_only_exists_here(
    forbid_effects: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    run(tmp_path)

    assert "1 diretório(s) carregam algo que só existe neste disco" in capsys.readouterr().out


# --- a tabela de despacho não pode divergir do vocabulário de ações -----------


def test_every_action_the_planner_emits_has_an_effect():
    """Uma ação nova sem efeito estouraria com KeyError na hora de aplicar.

    Não há ação manual neste script: tudo que ele planeja, ele sabe fazer. O que
    protege o operador não é a falta de efeito, é o `hold` do descarte.
    """
    emitted = {
        planner.CLONE_REPO,
        planner.REWRITE_REMOTE,
        planner.COMMIT_LOCAL,
        planner.PUSH_BRANCH,
        planner.PRESERVE_STASH,
        planner.DROP_STASH,
        planner.MOVE_REPO,
        planner.MOVE_WORKTREE,
        planner.REPAIR_WORKTREE,
        planner.DISCARD_DIR,
        planner.DISCARD_WORKTREE,
    }

    assert set(applier.build_effects()) == emitted


def test_a_move_lands_the_dir_at_the_address_the_plan_named(tmp_path: Path):
    """O único efeito que dá para exercitar sem rede nem repositório de verdade."""
    source = tmp_path / "workspaces" / "travelmanager"
    source.mkdir(parents=True)
    (source / "marca.txt").write_text("aqui\n", encoding="utf-8")
    destination = tmp_path / "workspaces" / ORG / "travelmanager"

    effects = applier.build_effects()
    effects[planner.MOVE_REPO](
        PlanItem(
            action=planner.MOVE_REPO,
            target=str(source),
            reason="repositório da org fora do diretório da org",
            payload={"to": str(destination)},
        )
    )

    assert (destination / "marca.txt").read_text(encoding="utf-8") == "aqui\n"
    assert not source.exists()
