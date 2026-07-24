"""O tipo de repositório é dado declarado, não inferido pelo checker."""

import json
from pathlib import Path

import pytest

from panlabs.checker.config import DEFAULT_REPO_TYPES_PATH, load_repo_types


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
