"""O planner do checker: dado o estado observado, qual matriz de deriva sai dele.

O planner é puro, e o que ele faz é **mecânica**: percorrer o catálogo, pular o
que não se aplica, converter falha de observação num veredito de erro e manter a
ordem estável. O conteúdo do catálogo é assunto de `test_checker_catalog.py`; aqui
o catálogo entra como argumento, feito à mão, para que um teste de mecânica não
mude de resultado quando alguém acrescenta um item de anatomia.

As fixtures são estado de repositório, não repositórios reais. Nada toca a rede.
"""

from typing import Any

from panlabs.checker import planner
from panlabs.checker.catalog import ORG, AnatomyItem
from panlabs.checker.catalog.item import always, has_file, has_surface, is_tipo, stack, tipo
from panlabs.checker.model import Observed
from panlabs.checker.observe import build_observed
from panlabs.plan import Plan, PlanItem

CATALOG = (
    AnatomyItem(
        id="readme-exists",
        scope=ORG,
        applies=always,
        satisfied=lambda repo: repo.has_readme,
        motivo=lambda repo: f"{repo.name} não tem README",
    ),
    AnatomyItem(
        id="python-runtime-declared",
        scope=stack("python"),
        applies=has_surface("python"),
        satisfied=has_file(".python-version"),
        motivo=lambda repo: f"{repo.name} tem superfície Python sem versão declarada",
    ),
    AnatomyItem(
        id="anatomy-doc-exists",
        scope=tipo("meta"),
        applies=is_tipo("meta"),
        satisfied=has_file("ANATOMY.md"),
        motivo=lambda repo: f"{repo.name} é do tipo meta e não tem ANATOMY.md",
    ),
)
"""Um catálogo mínimo com um item por eixo: o suficiente para exercitar a mecânica."""


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
    error: str | None = None,
) -> dict[str, Any]:
    if error is not None:
        return {"name": name, "error": error}
    return {"name": name, "tipo": tipo, "files": files or [], "has_readme": has_readme}


def observed(*repos: dict[str, Any]) -> Observed:
    return build_observed({"org": "panlabs-tech", "repos": list(repos)})


def plan_of(*repos: dict[str, Any]) -> Plan:
    return planner.plan(observed(*repos), CATALOG)


# --- escopo por eixo: o que não se aplica não gera linha nenhuma ---------------


def test_an_item_whose_scope_does_not_reach_the_repo_produces_no_row():
    the_plan = plan_of(repo("panlabs-tech/tfbox", files=["main.tf"]))

    assert actions_for(the_plan, "panlabs-tech/tfbox") == []


def test_a_manifest_in_a_subfolder_puts_the_repo_in_scope_for_the_surface_item():
    """O que a árvore recursiva mudou é **quem é avaliado**, não o que se exige."""
    the_plan = plan_of(repo("panlabs-tech/mono", files=["apps/api/pyproject.toml"]))

    assert actions_for(the_plan, "panlabs-tech/mono") == ["python-runtime-declared"]


def test_a_slot_buried_in_a_subfolder_does_not_satisfy_the_root_declaration():
    """A árvore inteira é observada, e é justamente por isso que o caminho importa."""
    the_plan = plan_of(repo("panlabs-tech/app", files=["pyproject.toml", "docs/.python-version"]))

    assert actions_for(the_plan, "panlabs-tech/app") == ["python-runtime-declared"]


def test_the_type_scoped_item_is_charged_only_against_its_declared_type():
    missing_doc = plan_of(repo("panlabs-tech/.github", tipo="meta", files=[]))
    present_doc = plan_of(repo("panlabs-tech/.github", tipo="meta", files=["ANATOMY.md"]))
    other_type = plan_of(repo("panlabs-tech/app", tipo="aplicacao", files=[]))

    assert actions_for(missing_doc, "panlabs-tech/.github") == ["anatomy-doc-exists"]
    assert actions_for(present_doc, "panlabs-tech/.github") == []
    assert actions_for(other_type, "panlabs-tech/app") == []


def test_an_unclassified_repo_is_reached_by_no_type_item_and_that_is_not_drift():
    the_plan = plan_of(repo("panlabs-tech/sem-tipo", tipo=None, files=[]))

    assert actions_for(the_plan, "panlabs-tech/sem-tipo") == []


# --- cada linha carrega item, escopo, veredito e motivo -----------------------


def test_every_row_carries_the_item_the_scope_the_verdict_and_the_reason():
    the_plan = plan_of(repo("panlabs-tech/nu", has_readme=False))

    item = items_for(the_plan, "panlabs-tech/nu")[0]
    assert item.action == "readme-exists"
    assert "README" in item.reason
    assert item.payload["scope"] == "invariante de org"
    assert item.payload["verdict"] == planner.DRIFT_VERDICT


def test_a_stack_scoped_row_names_the_surface_it_was_evaluated_on():
    """ "Reprovou por item de stack Python" é revisável; "reprovou" não é."""
    the_plan = plan_of(repo("panlabs-tech/app", files=["pyproject.toml"]))

    assert items_for(the_plan, "panlabs-tech/app")[0].payload["scope"] == "stack python"


# --- canal de erro, distinto de deriva ----------------------------------------


def test_an_observation_failure_yields_an_error_verdict_not_a_drift_verdict():
    the_plan = plan_of(repo("panlabs-tech/instavel", error="HTTP 401: bad credentials"))

    items = items_for(the_plan, "panlabs-tech/instavel")
    assert len(items) == 1
    assert items[0].payload["verdict"] == planner.ERROR_VERDICT
    assert items[0].payload["verdict"] != planner.DRIFT_VERDICT
    assert "bad credentials" in items[0].reason


def test_one_repos_observation_failure_does_not_swallow_the_others_drift():
    the_plan = plan_of(
        repo("panlabs-tech/instavel", error="timeout"),
        repo("panlabs-tech/nu", has_readme=False),
    )

    assert actions_for(the_plan, "panlabs-tech/instavel") == ["erro-observacao"]
    assert actions_for(the_plan, "panlabs-tech/nu") == ["readme-exists"]


def test_a_repo_that_failed_observation_is_evaluated_against_no_catalog_item():
    """Item que ninguém mediu não pode sair com cara de item que passou."""
    the_plan = plan_of(repo("panlabs-tech/truncado", error="árvore truncada"))

    assert actions_for(the_plan, "panlabs-tech/truncado") == ["erro-observacao"]


# --- alvo derivado e ordem estável ---------------------------------------------


def test_a_repo_new_to_the_live_org_enters_the_matrix_without_any_code_change():
    the_plan = plan_of(repo("panlabs-tech/recem-chegado", has_readme=False))

    assert actions_for(the_plan, "panlabs-tech/recem-chegado") == ["readme-exists"]


def test_a_dot_prefixed_repo_name_enters_the_matrix_like_any_other():
    the_plan = plan_of(repo("panlabs-tech/.github", tipo="meta", has_readme=False))

    assert "readme-exists" in actions_for(the_plan, "panlabs-tech/.github")


def test_the_plan_is_ordered_by_repo_name_whatever_order_the_org_listed_them_in():
    the_plan = plan_of(
        repo("panlabs-tech/zulu", has_readme=False),
        repo("panlabs-tech/alfa", has_readme=False),
        repo("panlabs-tech/mike", has_readme=False),
    )

    targets = [item.target for item in the_plan]

    assert targets == ["panlabs-tech/alfa", "panlabs-tech/mike", "panlabs-tech/zulu"]


def test_a_fully_conformant_repo_yields_no_rows_at_all():
    the_plan = plan_of(
        repo("panlabs-tech/.github", tipo="meta", files=["ANATOMY.md", ".python-version"])
    )

    assert actions_for(the_plan, "panlabs-tech/.github") == []
