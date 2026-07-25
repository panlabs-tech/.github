"""O planner do checker: dado o estado observado, qual matriz de deriva sai dele.

O planner é puro. As fixtures são estado de repositório, não repositórios
reais -- os casos que importam (superfície ausente, tipo não declarado) são
estados que a frota real não necessariamente está hoje.
"""

from typing import Any

from panlabs.checker import planner
from panlabs.checker.model import Observed
from panlabs.checker.observe import build_observed
from panlabs.plan import Plan, PlanItem


def items_for(the_plan: Plan, target: str) -> list[PlanItem]:
    return [item for item in the_plan if item.target == target]


def actions_for(the_plan: Plan, target: str) -> list[str]:
    return [item.action for item in items_for(the_plan, target)]


def repo(
    name: str,
    *,
    tipo: str | None = None,
    files: list[str] | None = None,
    has_readme: bool = True,
    has_license: bool = True,
    error: str | None = None,
) -> dict[str, Any]:
    if error is not None:
        return {"name": name, "error": error}
    return {
        "name": name,
        "tipo": tipo,
        "files": files or [],
        "has_readme": has_readme,
        "has_license": has_license,
    }


def observed(*repos: dict[str, Any]) -> Observed:
    return build_observed({"org": "panlabs-tech", "repos": list(repos)})


# --- escopo por eixo: stack não cobra o que não se aplica ---------------------


def test_a_terraform_only_repo_is_not_failed_by_a_node_scoped_item():
    state = observed(repo("panlabs-tech/tfbox", files=["main.tf", "README.md", "LICENSE"]))

    the_plan = planner.plan(state)

    assert "node-lockfile-committed" not in actions_for(the_plan, "panlabs-tech/tfbox")


def test_a_repo_with_no_surface_at_all_is_not_failed_for_a_missing_stack_leg():
    state = observed(repo("panlabs-tech/skills", files=["README.md", "LICENSE"]))

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/skills") == []


def test_the_node_surface_of_a_monorepo_is_charged_for_the_lockfile_beside_its_manifest():
    """O lockfile de um monorepo mora junto do manifesto, não na raiz do repo.

    Exigir a raiz reprovaria o layout que a própria anatomia manda uma aplicação
    ter. O que a stack cobra é lockfile versionado, não lockfile na raiz.
    """
    state = observed(repo("panlabs-tech/mono", files=["web/package.json", "web/package-lock.json"]))

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/mono") == []


def test_a_node_surface_with_no_lockfile_anywhere_is_drift_like_before():
    state = observed(repo("panlabs-tech/mono", files=["web/package.json"]))

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/mono") == ["node-lockfile-committed"]


def test_a_runtime_slot_buried_in_a_subfolder_does_not_satisfy_the_root_declaration():
    """A árvore inteira é observada, e é justamente por isso que o caminho importa.

    O gerenciador de runtime da máquina lê a declaração na raiz do repo; uma
    homônima enterrada numa subpasta não é a mesma declaração.
    """
    state = observed(repo("panlabs-tech/app", files=["pyproject.toml", "docs/.python-version"]))

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/app") == ["python-runtime-declared"]


def test_a_repo_with_two_surfaces_is_evaluated_on_both():
    state = observed(repo("panlabs-tech/monorepo", files=["pyproject.toml", "package.json"]))

    the_plan = planner.plan(state)

    actions = actions_for(the_plan, "panlabs-tech/monorepo")
    assert "python-runtime-declared" in actions
    assert "node-lockfile-committed" in actions


# --- invariante versus condicional --------------------------------------------


def test_a_missing_invariant_item_shows_up_as_drift_with_a_reason_naming_it():
    state = observed(repo("panlabs-tech/nu", has_readme=False))

    the_plan = planner.plan(state)

    item = items_for(the_plan, "panlabs-tech/nu")[0]
    assert item.action == "readme-exists"
    assert "README" in item.reason
    assert item.payload["scope"] == "invariante de org"
    assert item.payload["verdict"] == planner.DRIFT_VERDICT


def test_a_conditional_item_legitimately_out_of_scope_does_not_appear_at_all():
    state = observed(repo("panlabs-tech/panlabs", tipo="aplicacao", files=[]))

    the_plan = planner.plan(state)

    assert "anatomy-doc-exists" not in actions_for(the_plan, "panlabs-tech/panlabs")


def test_the_type_scoped_item_is_charged_only_against_its_declared_type():
    missing = observed(repo("panlabs-tech/.github", tipo="meta", files=["README.md"]))
    present = observed(repo("panlabs-tech/.github", tipo="meta", files=["README.md", "ANATOMY.md"]))

    assert actions_for(planner.plan(missing), "panlabs-tech/.github") == ["anatomy-doc-exists"]
    assert actions_for(planner.plan(present), "panlabs-tech/.github") == []


# --- canal de erro, distinto de deriva ----------------------------------------


def test_an_observation_failure_yields_an_error_verdict_not_a_drift_verdict():
    state = observed(repo("panlabs-tech/instavel", error="HTTP 401: bad credentials"))

    the_plan = planner.plan(state)

    items = items_for(the_plan, "panlabs-tech/instavel")
    assert len(items) == 1
    assert items[0].payload["verdict"] == planner.ERROR_VERDICT
    assert items[0].payload["verdict"] != planner.DRIFT_VERDICT
    assert "bad credentials" in items[0].reason


def test_one_repos_observation_failure_does_not_swallow_the_others_drift():
    state = observed(
        repo("panlabs-tech/instavel", error="timeout"),
        repo("panlabs-tech/nu", has_license=False),
    )

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/instavel") == ["erro-observacao"]
    assert actions_for(the_plan, "panlabs-tech/nu") == ["license-exists"]


# --- alvo derivado e ordem estável ---------------------------------------------


def test_a_repo_new_to_the_live_org_enters_the_matrix_without_any_code_change():
    state = observed(repo("panlabs-tech/recem-chegado", has_readme=False))

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/recem-chegado") == ["readme-exists"]


def test_a_dot_prefixed_repo_name_enters_the_matrix_like_any_other():
    state = observed(repo("panlabs-tech/.github", tipo="meta", files=[], has_license=False))

    the_plan = planner.plan(state)

    assert "license-exists" in actions_for(the_plan, "panlabs-tech/.github")


def test_the_plan_is_ordered_by_repo_name_whatever_order_the_org_listed_them_in():
    state = observed(
        repo("panlabs-tech/zulu", has_readme=False),
        repo("panlabs-tech/alfa", has_readme=False),
        repo("panlabs-tech/mike", has_readme=False),
    )

    targets = [item.target for item in planner.plan(state)]

    assert targets == ["panlabs-tech/alfa", "panlabs-tech/mike", "panlabs-tech/zulu"]


def test_a_fully_conformant_repo_yields_no_rows_at_all():
    state = observed(
        repo(
            "panlabs-tech/.github",
            tipo="meta",
            files=["README.md", "LICENSE", "ANATOMY.md", "pyproject.toml", ".python-version"],
        )
    )

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/.github") == []
