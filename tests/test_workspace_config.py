"""A configuração desejada do espaço de trabalho, lida como dado versionado.

O que se testa aqui é o que separa "ainda não decidido" de "decidido como vazio",
e as duas validações que impedem um dado plausível e errado de virar plano: um
molde de remote sem os campos que o distinguem produziria o mesmo endereço para a
org inteira, e um caminho absoluto de worktree poria as árvores de repositórios
diferentes no mesmo lugar.
"""

import json
from pathlib import Path

import pytest

from panlabs.workspace.config import DEFAULT_CONFIG_PATH, Desired, load_desired

REMOTE = "https://github.com/{org}/{name}.git"


def written(tmp_path: Path, body: dict[str, object]) -> Path:
    path = tmp_path / "workspace.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_a_null_dimension_reads_as_undecided_and_an_empty_list_does_not(tmp_path: Path):
    desired = load_desired(written(tmp_path, {"migrated_from": [], "worktrees": None}))

    assert desired.migrated_from == ()
    assert "migrated_from" not in desired.undecided
    assert "worktrees" in desired.undecided


def test_a_config_with_every_dimension_decided_reports_nothing_undecided(tmp_path: Path):
    desired = load_desired(
        written(
            tmp_path,
            {
                "root": "~/workspaces",
                "remote": REMOTE,
                "migrated_from": ["ThiagoPanini"],
                "worktrees": ".claude/worktrees",
            },
        )
    )

    assert desired.is_decided


def test_the_root_arrives_expanded_because_the_planner_compares_absolute_paths(tmp_path: Path):
    desired = load_desired(written(tmp_path, {"root": "~/workspaces"}))

    assert desired.root == str(Path.home() / "workspaces")


def test_an_unknown_key_is_an_error_and_not_a_silently_ignored_line(tmp_path: Path):
    with pytest.raises(ValueError, match="chave desconhecida"):
        load_desired(written(tmp_path, {"raiz": "~/workspaces"}))


def test_a_remote_template_without_both_fields_is_refused(tmp_path: Path):
    """Um molde sem os campos produziria o mesmo endereço para a org inteira."""
    with pytest.raises(ValueError, match=r"\{name\}"):
        load_desired(written(tmp_path, {"remote": "https://github.com/{org}/repo.git"}))


def test_an_absolute_worktree_path_is_refused(tmp_path: Path):
    """Absoluto poria as árvores de repositórios diferentes no mesmo lugar."""
    with pytest.raises(ValueError, match="relativo"):
        load_desired(written(tmp_path, {"worktrees": "~/worktrees"}))


def test_the_canonical_url_is_built_from_the_versioned_template(tmp_path: Path):
    desired = load_desired(written(tmp_path, {"remote": REMOTE}))

    assert desired.url_for("panlabs-tech", ".github") == (
        "https://github.com/panlabs-tech/.github.git"
    )


def test_an_undecided_remote_builds_no_url_at_all():
    assert Desired().url_for("panlabs-tech", "skills") == ""


# --- o dado que este repo entrega ---------------------------------------------


def test_the_shipped_config_is_readable_and_fully_decided():
    """O dado versionado é o que roda na máquina viva; ele precisa carregar inteiro."""
    desired = load_desired(DEFAULT_CONFIG_PATH)

    assert desired.is_decided
    assert desired.migrated_from == ("ThiagoPanini",)
    assert desired.url_for("panlabs-tech", "skills") == (
        "https://github.com/panlabs-tech/skills.git"
    )
