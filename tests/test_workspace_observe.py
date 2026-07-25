"""A observação do espaço de trabalho: o que o disco e o git dizem, antes de decidir.

Os testes que importam aqui são os dois em que o **default do git mente**, e mente
em direções opostas. Eles usam repositório de verdade em diretório temporário,
porque o que está sob teste é justamente a leitura, e uma fixture de leitura
provaria só que a fixture concorda consigo mesma.
"""

import subprocess
from pathlib import Path

from panlabs.workspace import observe
from panlabs.workspace.model import EMPTY, PLAIN, REPO, WORKTREE


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    )
    return done.stdout


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "op@example.test")
    git(path, "config", "user.name", "Operador")
    git(path, "config", "commit.gpgsign", "false")
    (path / "README.md").write_text("inicial\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "inicial")
    return path


def look(path: Path) -> dict[str, object]:
    return observe._look_at(path)  # pyright: ignore[reportPrivateUsage]


# --- o status colapsa diretório não rastreado e subconta ----------------------


def test_content_detection_finds_every_file_a_collapsed_dir_would_hide(tmp_path: Path):
    """O default do git reporta `rascunho/` como um item só; são três arquivos."""
    repo = make_repo(tmp_path / "campfire")
    (repo / "rascunho").mkdir()
    for name in ("a.md", "b.md", "c.md"):
        (repo / "rascunho" / name).write_text("x\n", encoding="utf-8")

    entry = look(repo)

    assert entry["dirty"] == ["rascunho/a.md", "rascunho/b.md", "rascunho/c.md"]


def test_what_git_ignores_never_enters_the_preservation_plan(tmp_path: Path):
    """A cláusula que faz o eixo terminar em vez de virar arqueologia infinita."""
    repo = make_repo(tmp_path / "campfire")
    (repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "pesado.js").write_text("x\n", encoding="utf-8")

    entry = look(repo)

    assert entry["dirty"] == [".gitignore"]


def test_a_renamed_file_is_reported_once_and_by_its_new_name(tmp_path: Path):
    repo = make_repo(tmp_path / "campfire")
    git(repo, "mv", "README.md", "LEIAME.md")

    entry = look(repo)

    assert entry["dirty"] == ["LEIAME.md"]


def test_a_clean_repo_reports_nothing_dirty(tmp_path: Path):
    entry = look(make_repo(tmp_path / "campfire"))

    assert entry["dirty"] == []


# --- a comparação por identificador superconta sob squash-merge ---------------


def test_a_branch_landed_by_squash_merge_reads_as_content_on_the_remote(tmp_path: Path):
    """O alarme falso já sofrido, reproduzido: o identificador diverge, a árvore não.

    O remote recebe o mesmo conteúdo por um commit **novo**, exatamente como um
    squash-merge o faria. A branch local continua apontando para o commit antigo.
    """
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    repo = make_repo(tmp_path / "travelmanager")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")

    git(repo, "checkout", "-qb", "feat/212")
    (repo / "novo.md").write_text("trabalho\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "trabalho")

    # O squash: o mesmo conteúdo aterrissa na main com outro identificador.
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--squash", "feat/212")
    git(repo, "commit", "-qm", "squash de feat/212")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "checkout", "-q", "feat/212")

    entry = look(repo)
    branch = next(b for b in entry["branches"] if b["name"] == "feat/212")  # pyright: ignore

    assert branch["content_on_remote"] is True
    assert branch["commit_on_remote"] is False


def test_a_branch_that_never_left_the_disk_reads_as_absent_from_the_remote(tmp_path: Path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    repo = make_repo(tmp_path / "campfire")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")

    git(repo, "checkout", "-qb", "mvp/lofi")
    (repo / "so-aqui.md").write_text("nunca subiu\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "so aqui")

    entry = look(repo)
    branch = next(b for b in entry["branches"] if b["name"] == "mvp/lofi")  # pyright: ignore

    assert branch["content_on_remote"] is False


# --- o que cada diretório é ---------------------------------------------------


def test_an_empty_dir_and_a_dir_without_git_are_told_apart(tmp_path: Path):
    (tmp_path / "luc-wt").mkdir()
    (tmp_path / "hashnode-backup").mkdir()
    (tmp_path / "hashnode-backup" / "post.md").write_text("x\n", encoding="utf-8")

    assert look(tmp_path / "luc-wt")["kind"] == EMPTY
    assert look(tmp_path / "hashnode-backup")["kind"] == PLAIN


def test_a_worktree_names_the_parent_it_hangs_from(tmp_path: Path):
    repo = make_repo(tmp_path / "travelmanager")
    git(repo, "worktree", "add", "-q", "-b", "feat/212", str(tmp_path / "wt-212"))

    entry = look(tmp_path / "wt-212")

    assert entry["kind"] == WORKTREE
    assert entry["parent"] == str(repo)
    assert look(repo)["kind"] == REPO


def test_a_worktree_reports_only_the_branch_it_carries(tmp_path: Path):
    """As outras branches são do pai, e contá-las duas vezes duplicaria o push."""
    repo = make_repo(tmp_path / "travelmanager")
    git(repo, "branch", "outra")
    git(repo, "worktree", "add", "-q", "-b", "feat/212", str(tmp_path / "wt-212"))

    entry = look(tmp_path / "wt-212")

    assert [b["name"] for b in entry["branches"]] == ["feat/212"]  # pyright: ignore
    assert sorted(b["name"] for b in look(repo)["branches"]) == [  # pyright: ignore
        "feat/212",
        "main",
        "outra",
    ]


def test_only_the_repository_reports_the_stash_that_both_share(tmp_path: Path):
    repo = make_repo(tmp_path / "travelmanager")
    (repo / "README.md").write_text("mexido\n", encoding="utf-8")
    git(repo, "stash", "push", "-q", "-m", "trabalho parado")
    git(repo, "worktree", "add", "-q", "-b", "feat/212", str(tmp_path / "wt-212"))

    assert len(look(repo)["stashes"]) == 1  # pyright: ignore
    assert "stashes" not in look(tmp_path / "wt-212")


def test_a_stash_of_a_branch_that_is_gone_reads_as_orphan(tmp_path: Path):
    repo = make_repo(tmp_path / "campfire")
    git(repo, "checkout", "-qb", "visual-reset")
    (repo / "README.md").write_text("mexido\n", encoding="utf-8")
    git(repo, "stash", "push", "-q", "-m", "poster")
    git(repo, "checkout", "-q", "main")
    git(repo, "branch", "-qD", "visual-reset")

    (stash,) = look(repo)["stashes"]  # pyright: ignore

    assert stash["branch"] == "visual-reset"
    assert stash["branch_alive"] is False


def test_a_stash_of_a_branch_that_is_still_there_reads_as_alive(tmp_path: Path):
    repo = make_repo(tmp_path / "campfire")
    (repo / "README.md").write_text("mexido\n", encoding="utf-8")
    git(repo, "stash", "push", "-q", "-m", "trabalho parado")

    (stash,) = look(repo)["stashes"]  # pyright: ignore

    assert stash["branch"] == "main"
    assert stash["branch_alive"] is True


# --- a varredura da raiz ------------------------------------------------------


def test_the_org_mirror_dir_is_not_a_candidate_and_its_children_are(tmp_path: Path):
    """O agrupador não é diretório comum; tratá-lo assim o poria na conta da faxina."""
    root = tmp_path / "workspaces"
    (root / "panlabs-tech" / ".github").mkdir(parents=True)
    (root / "panlabs-tech" / "skills").mkdir()
    (root / "b3stocks").mkdir()

    found = [
        str(path)
        for path in observe._candidates(root, "panlabs-tech")  # pyright: ignore[reportPrivateUsage]
    ]

    assert found == [
        str(root / "b3stocks"),
        str(root / "panlabs-tech" / ".github"),
        str(root / "panlabs-tech" / "skills"),
    ]


def test_a_worktree_outside_the_root_is_left_alone(tmp_path: Path):
    """Árvore em diretório temporário é transitória; o invariante é do espaço."""
    root = tmp_path / "workspaces"
    root.mkdir()
    repo = make_repo(root / "travelmanager")
    git(repo, "worktree", "add", "-q", "-b", "fora", str(tmp_path / "outro-lugar"))
    git(repo, "worktree", "add", "-q", "-b", "dentro", str(root / "wt-1"))

    found = observe._worktrees_of(repo, root)  # pyright: ignore[reportPrivateUsage]

    assert [entry["path"] for entry in found] == [str(root / "wt-1")]


def test_the_raw_snapshot_round_trips_through_the_observed_type(tmp_path: Path):
    """O retrato salvo é o que vira fixture, e precisa voltar igual ao que saiu."""
    root = tmp_path / "workspaces"
    root.mkdir()
    make_repo(root / "campfire")
    raw = {
        "org": "panlabs-tech",
        "root": str(root),
        "org_repos": ["skills"],
        "dirs": [look(root / "campfire")],
    }

    observed = observe.build_observed(raw)

    assert observe.observed_to_dict(observed)["dirs"][0]["path"] == str(root / "campfire")
    assert observed.org_repos == ("skills",)
