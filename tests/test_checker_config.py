"""O dado que a observação lê: o tipo de cada repo, e o conjunto de arquivos lidos.

Nenhum dos dois é inferido pelo checker. O tipo é escolha do operador quando o
repositório nasce; o conjunto de arquivos cujo **conteúdo** é lido é declarado,
porque a alternativa seria varredura cega e uma chamada por arquivo.
"""

import json
from pathlib import Path

import pytest

from panlabs.checker.config import (
    DEFAULT_CHECKER_CONFIG_PATH,
    DEFAULT_REPO_TYPES_PATH,
    load_read_files,
    load_repo_types,
)


def test_the_config_shipped_in_this_repo_declares_dot_github_as_meta():
    types = load_repo_types(DEFAULT_REPO_TYPES_PATH)

    assert types["panlabs-tech/.github"] == "meta"


def test_a_null_type_is_treated_as_not_yet_classified_not_as_a_type_named_null(tmp_path: Path):
    path = tmp_path / "repo-types.json"
    path.write_text(json.dumps({"panlabs-tech/panlabs": None}), encoding="utf-8")

    types = load_repo_types(path)

    assert "panlabs-tech/panlabs" not in types


def test_keys_prefixed_with_underscore_are_notes_for_humans_and_are_ignored(tmp_path: Path):
    path = tmp_path / "repo-types.json"
    path.write_text(json.dumps({"_nota": "qualquer coisa"}), encoding="utf-8")

    assert load_repo_types(path) == {}


def test_a_type_outside_the_five_named_in_anatomy_fails_loudly_instead_of_silently(
    tmp_path: Path,
):
    path = tmp_path / "repo-types.json"
    path.write_text(json.dumps({"panlabs-tech/panlabs": "aplicaçao"}), encoding="utf-8")

    with pytest.raises(ValueError, match="aplicaçao"):
        load_repo_types(path)


# --- o conjunto de arquivos cujo conteúdo é lido ------------------------------


def test_the_shipped_config_declares_which_files_have_their_content_read():
    assert load_read_files(DEFAULT_CHECKER_CONFIG_PATH)


def test_every_declared_path_is_relative_to_the_repo_root(tmp_path: Path):
    """Um caminho absoluto seria da máquina, e o que se lê é o conteúdo do repo."""
    for path in load_read_files(DEFAULT_CHECKER_CONFIG_PATH):
        assert not path.startswith("/"), path


def test_an_undeclared_set_reads_nothing_instead_of_sweeping_the_repo(tmp_path: Path):
    path = tmp_path / "checker.json"
    path.write_text(json.dumps({"read_files": None}), encoding="utf-8")

    assert load_read_files(path) == ()


def test_an_unknown_key_is_refused_instead_of_ignored(tmp_path: Path):
    path = tmp_path / "checker.json"
    path.write_text(json.dumps({"arquivos": ["AGENTS.md"]}), encoding="utf-8")

    with pytest.raises(ValueError, match="chave desconhecida"):
        load_read_files(path)


def test_a_repeated_path_is_refused_because_it_would_pay_twice_for_one_answer(tmp_path: Path):
    path = tmp_path / "checker.json"
    path.write_text(json.dumps({"read_files": ["AGENTS.md", "AGENTS.md"]}), encoding="utf-8")

    with pytest.raises(ValueError, match="repetido"):
        load_read_files(path)
