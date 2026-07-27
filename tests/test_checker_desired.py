"""O punhado de valores decididos que a anatomia compara, e o que `null` significa.

O catálogo é código, e a maior parte dos itens não compara contra valor nenhum.
Três comparam: licença uniforme e os dois majors de runtime convergidos. E uma
quarta dimensão o checker **não** decide -- ele lê de `config/org.json`, pelo mesmo
loader do script de org, porque duplicar a lista de exceção de wiki criaria duas
verdades que divergem no dia em que uma for editada.

O que estes testes guardam é a distinção que o repo inteiro carrega: não decidido
não é decidido-como-vazio, e nenhum dos dois é conforme.
"""

import json
from pathlib import Path

import pytest

from panlabs.checker.desired import DEFAULT_ANATOMY_PATH, Desired, load_desired
from panlabs.org.config import DEFAULT_CONFIG_PATH as ORG_CONFIG_PATH


def anatomy(tmp_path: Path, **values: object) -> Path:
    path = tmp_path / "anatomy.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def test_the_shipped_data_loads_and_its_undecided_dimensions_are_named():
    desired = load_desired()

    assert set(desired.undecided) <= {"license", "python_series", "node_series"}


def test_a_null_dimension_is_undecided_and_shows_up_as_such(tmp_path: Path):
    desired = load_desired(anatomy(tmp_path, license=None), ORG_CONFIG_PATH)

    assert desired.license is None
    assert "license" in desired.undecided


def test_a_decided_dimension_leaves_the_undecided_list(tmp_path: Path):
    desired = load_desired(anatomy(tmp_path, license="MIT"), ORG_CONFIG_PATH)

    assert desired.license == "MIT"
    assert "license" not in desired.undecided


def test_an_unknown_key_is_refused_instead_of_silently_ignored(tmp_path: Path):
    """Uma chave com typo que passasse calada seria uma decisão que ninguém aplica."""
    with pytest.raises(ValueError, match="chave desconhecida"):
        load_desired(anatomy(tmp_path, licence="MIT"), ORG_CONFIG_PATH)


def test_the_wiki_dimension_is_read_from_the_org_data_and_never_from_here(tmp_path: Path):
    """A decisão continua na spec de Org; o que atravessa para cá é a vigia."""
    desired = load_desired(anatomy(tmp_path), ORG_CONFIG_PATH)

    assert desired.wiki is False
    assert desired.wiki_exceptions


def test_an_org_config_with_no_wiki_decision_leaves_the_item_unevaluated(tmp_path: Path):
    org = tmp_path / "org.json"
    org.write_text(json.dumps({"wiki": None}), encoding="utf-8")

    desired = load_desired(anatomy(tmp_path), org)

    assert desired.wiki is None
    assert desired.wiki_exceptions == frozenset()


def test_the_default_desired_has_nothing_decided_at_all():
    """O default do planner não pode inventar decisão que ninguém tomou."""
    assert Desired().undecided == ("license", "node_series", "python_series")


def test_the_shipped_anatomy_data_lives_next_to_the_other_configuration():
    assert DEFAULT_ANATOMY_PATH.name == "anatomy.json"
    assert DEFAULT_ANATOMY_PATH.parent == ORG_CONFIG_PATH.parent
