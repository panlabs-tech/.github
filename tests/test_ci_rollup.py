"""O contrato de nomes de status check: a correção ao defeito do #59.

O que é testado aqui não é workflow nenhum (nenhum roda), é a composição pura:
o conjunto de nomes publicados não pode variar com a superfície, e uma perna
reprovada precisa reprovar o rollup, não ser pulada.
"""

from panlabs.ci import rollup

# --- o conjunto de nomes publicados não varia com a superfície ----------------


def test_a_repo_with_zero_surfaces_still_publishes_the_rollup_and_security_names():
    names = rollup.required_status_names([])

    assert names == {"checks", "security"}


def test_a_repo_with_one_surface_publishes_the_same_two_names_as_zero_surfaces():
    names = rollup.required_status_names(["python"])

    assert names == {"checks", "security"}


def test_a_repo_with_two_surfaces_publishes_the_same_two_names_as_zero_and_one():
    names = rollup.required_status_names(["python", "node"])

    assert names == {"checks", "security"}


def test_the_published_name_set_is_identical_across_zero_one_and_two_surfaces():
    """O teste que teria pego o defeito original do #59."""
    zero = rollup.required_status_names([])
    one = rollup.required_status_names(["python"])
    two = rollup.required_status_names(["python", "node"])

    assert zero == one == two


def test_the_rollup_needs_list_grows_with_surfaces_while_its_published_name_does_not():
    job = rollup.build_rollup(["python", "node"])

    assert job.name == "checks"
    assert job.needs == ("checks-python", "checks-node")


def test_a_surface_less_repo_has_an_empty_needs_list_on_a_rollup_that_still_exists():
    job = rollup.build_rollup([])

    assert job.name == "checks"
    assert job.needs == ()


# --- uma perna reprovada reprova o rollup, não o pula --------------------------


def test_a_single_failed_leg_fails_the_rollup_instead_of_being_skipped():
    conclusion = rollup.rollup_conclusion({"checks-python": "failure"})

    assert conclusion == "failure"


def test_one_failed_leg_among_several_passing_ones_still_fails_the_rollup():
    conclusion = rollup.rollup_conclusion({"checks-python": "success", "checks-node": "failure"})

    assert conclusion == "failure"


def test_all_legs_passing_yields_a_successful_rollup():
    conclusion = rollup.rollup_conclusion({"checks-python": "success", "checks-node": "success"})

    assert conclusion == "success"


def test_a_skipped_leg_does_not_by_itself_fail_the_rollup():
    conclusion = rollup.rollup_conclusion({"checks-python": "success", "checks-node": "skipped"})

    assert conclusion == "success"


def test_a_repo_with_no_legs_at_all_yields_a_trivially_successful_rollup():
    conclusion = rollup.rollup_conclusion({})

    assert conclusion == "success"


def test_a_cancelled_leg_fails_the_rollup_because_only_success_and_skipped_are_safe():
    conclusion = rollup.rollup_conclusion({"checks-python": "cancelled"})

    assert conclusion == "failure"
