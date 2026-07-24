"""O planner do ruleset: dado o estado observado, quais divergências viram plano.

O planner é puro. Nada aqui toca rede, token ou disco além das fixtures — e é
justamente isso que permite exercitar o caminho destrutivo sem destruir nada.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from panlabs.plan import Plan, PlanItem
from panlabs.ruleset import planner
from panlabs.ruleset.config import Desired, load_desired
from panlabs.ruleset.model import Observed
from panlabs.ruleset.observe import build_observed

FIXTURES = Path(__file__).parent / "fixtures"
FLEET = FIXTURES / "fleet-2026-07-24.json"


def load_fleet_raw() -> dict[str, Any]:
    return json.loads(FLEET.read_text(encoding="utf-8"))


def fleet() -> Observed:
    return build_observed(load_fleet_raw())


def desired() -> Desired:
    return load_desired(FIXTURES / "desired-ruleset.json")


def items_for(plan: Plan, target: str) -> list[PlanItem]:
    return [item for item in plan if item.target == target]


def actions_for(plan: Plan, target: str) -> list[str]:
    return [item.action for item in items_for(plan, target)]


def echo_ruleset(body: Mapping[str, Any], ruleset_id: int = 1) -> dict[str, Any]:
    """O ruleset como o GitHub o devolve depois de aplicado.

    A API preenche defaults que não foram enviados e anexa metadados próprios.
    Um planner que não tolerasse esse ruído acusaria divergência a cada leitura,
    e o script nunca convergiria — por isso a idempotência se testa contra o eco,
    não contra o corpo enviado.
    """
    defaults: dict[str, dict[str, Any]] = {
        "pull_request": {
            "dismiss_stale_reviews_on_push": False,
            "dismissal_restriction": {"allowed_actors": [], "enabled": False},
            "require_code_owner_review": False,
            "require_last_push_approval": False,
            "required_review_thread_resolution": False,
            "required_reviewers": [],
        },
        "required_status_checks": {"do_not_enforce_on_create": False},
    }

    rules: list[dict[str, Any]] = []
    for rule in body["rules"]:
        params = {**defaults.get(rule["type"], {}), **rule.get("parameters", {})}
        rules.append({"type": rule["type"], **({"parameters": params} if params else {})})

    return {
        "id": ruleset_id,
        "name": body["name"],
        "target": body["target"],
        "enforcement": body["enforcement"],
        "bypass_actors": body["bypass_actors"],
        "conditions": body["conditions"],
        "rules": rules,
        "node_id": "RRS_fixture",
        "source": "panlabs-tech/fixture",
        "source_type": "Repository",
        "created_at": "2026-07-24T00:00:00Z",
        "updated_at": "2026-07-24T00:00:00Z",
        "_links": {"self": {"href": "https://api.github.com/x"}},
    }


def repo(
    name: str,
    *,
    rulesets: list[dict[str, Any]] | None = None,
    classic_protection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "default_branch": "main",
        "rulesets": rulesets or [],
        "classic_protection": classic_protection,
    }


def observed(*repos: dict[str, Any]) -> Observed:
    return build_observed({"org": "panlabs-tech", "repos": list(repos)})


CLASSIC = {
    "required_status_checks": {"strict": False, "contexts": ["web", "security"]},
    "required_pull_request_reviews": {"required_approving_review_count": 0},
    "required_signatures": {"enabled": False},
    "enforce_admins": {"enabled": False},
    "required_linear_history": {"enabled": False},
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
}


# --- idempotência -------------------------------------------------------------


def test_repo_already_matching_the_desired_ruleset_yields_an_empty_plan():
    want = desired()
    assert want.ruleset is not None
    state = observed(repo("panlabs-tech/conforme", rulesets=[echo_ruleset(want.ruleset)]))

    plan = planner.plan(state, want)

    assert not plan
    assert plan.render().startswith("Nada a fazer")


def test_replanning_after_a_create_yields_nothing_because_the_ruleset_now_matches():
    want = desired()
    assert want.ruleset is not None
    before = observed(repo("panlabs-tech/skills"))

    first = planner.plan(before, want)
    applied = first.items[0].payload["body"]
    after = observed(repo("panlabs-tech/skills", rulesets=[echo_ruleset(applied)]))

    assert actions_for(first, "panlabs-tech/skills") == [planner.CREATE_RULESET]
    assert not planner.plan(after, want)


# --- criação e divergência ----------------------------------------------------


def test_repo_without_any_ruleset_yields_a_create_carrying_the_body_to_send():
    want = desired()
    state = observed(repo("panlabs-tech/skills"))

    plan = planner.plan(state, want)

    assert len(plan) == 1
    item = plan.items[0]
    assert item.action == planner.CREATE_RULESET
    assert item.target == "panlabs-tech/skills"
    assert "main" in item.reason
    assert item.payload["body"] == want.ruleset


def test_divergent_merge_methods_yield_an_update_whose_reason_names_the_field():
    want = desired()
    assert want.ruleset is not None
    echoed = echo_ruleset(want.ruleset, ruleset_id=42)
    for rule in echoed["rules"]:
        if rule["type"] == "pull_request":
            rule["parameters"]["allowed_merge_methods"] = ["merge", "squash", "rebase"]
    state = observed(repo("panlabs-tech/frouxo", rulesets=[echoed]))

    plan = planner.plan(state, want)

    assert len(plan) == 1
    item = plan.items[0]
    assert item.action == planner.UPDATE_RULESET
    assert "allowed_merge_methods" in item.reason
    assert "squash" in item.reason
    assert item.payload["ruleset_id"] == 42
    assert item.payload["body"] == want.ruleset


def test_missing_rule_is_named_as_absent_and_extra_rule_is_named_as_undesired():
    want = desired()
    assert want.ruleset is not None
    echoed = echo_ruleset(want.ruleset)
    echoed["rules"] = [r for r in echoed["rules"] if r["type"] != "required_signatures"]
    echoed["rules"].append({"type": "creation"})
    state = observed(repo("panlabs-tech/torto", rulesets=[echoed]))

    plan = planner.plan(state, want)

    reason = plan.items[0].reason
    assert "required_signatures" in reason
    assert "creation" in reason


def test_a_ruleset_that_does_not_govern_the_default_branch_does_not_count_as_convergence():
    want = desired()
    assert want.ruleset is not None
    unrelated = echo_ruleset(want.ruleset)
    unrelated["conditions"] = {"ref_name": {"include": ["refs/heads/release/*"], "exclude": []}}
    state = observed(repo("panlabs-tech/outro", rulesets=[unrelated]))

    plan = planner.plan(state, want)

    assert actions_for(plan, "panlabs-tech/outro") == [planner.CREATE_RULESET]


def test_a_tag_ruleset_is_ignored_because_it_does_not_govern_the_default_branch():
    want = desired()
    assert want.ruleset is not None
    tag_ruleset = echo_ruleset(want.ruleset)
    tag_ruleset["target"] = "tag"
    state = observed(repo("panlabs-tech/tags", rulesets=[tag_ruleset]))

    plan = planner.plan(state, want)

    assert actions_for(plan, "panlabs-tech/tags") == [planner.CREATE_RULESET]


# --- proteção clássica --------------------------------------------------------


def test_repo_with_classic_protection_yields_an_item_that_retires_it():
    want = desired()
    assert want.ruleset is not None
    state = observed(
        repo(
            "panlabs-tech/legado",
            rulesets=[echo_ruleset(want.ruleset)],
            classic_protection=CLASSIC,
        )
    )

    plan = planner.plan(state, want)

    assert len(plan) == 1
    item = plan.items[0]
    assert item.action == planner.DELETE_CLASSIC_PROTECTION
    assert item.payload["branch"] == "main"
    assert "web" in item.reason and "security" in item.reason
    assert "administrador" in item.reason


def test_a_strict_classic_protection_names_strictness_in_the_reason_that_retires_it():
    """O motivo apaga uma garantia, então precisa nomear cada uma que existia."""
    want = desired()
    strict_classic = {
        **CLASSIC,
        "required_status_checks": {"strict": True, "contexts": ["web"]},
    }
    state = observed(repo("panlabs-tech/estrito", classic_protection=strict_classic))

    plan = planner.plan(state, want)

    reason = items_for(plan, "panlabs-tech/estrito")[-1].reason
    assert "estrito" in reason


def test_classic_protection_is_left_alone_when_the_desired_state_does_not_ask_to_retire_it():
    want = Desired(ruleset=None, retire_classic_protection=False)
    state = observed(repo("panlabs-tech/legado", classic_protection=CLASSIC))

    assert not planner.plan(state, want)


# --- coerência: um plano por branch, não dois --------------------------------


def test_repo_with_ruleset_and_classic_protection_yields_one_action_per_source_not_two_rulesets():
    """O caso real do tfbox: ruleset e proteção clássica sobre a mesma branch."""
    want = desired()
    state = build_observed(
        {
            "org": "panlabs-tech",
            "repos": [r for r in load_fleet_raw()["repos"] if r["name"] == "panlabs-tech/tfbox"],
        }
    )

    plan = planner.plan(state, want)
    actions = actions_for(plan, "panlabs-tech/tfbox")

    assert actions == [planner.UPDATE_RULESET, planner.DELETE_CLASSIC_PROTECTION]
    assert planner.CREATE_RULESET not in actions
    assert {item.target for item in plan} == {"panlabs-tech/tfbox"}


def test_a_second_ruleset_governing_the_same_branch_is_planned_for_deletion():
    want = desired()
    assert want.ruleset is not None
    first = echo_ruleset(want.ruleset, ruleset_id=10)
    second = echo_ruleset(want.ruleset, ruleset_id=20)
    second["name"] = "main protection"
    state = observed(repo("panlabs-tech/duplo", rulesets=[first, second]))

    plan = planner.plan(state, want)

    assert actions_for(plan, "panlabs-tech/duplo") == [planner.DELETE_RULESET]
    item = plan.items[0]
    assert item.payload["ruleset_id"] == 20
    assert "main protection" in item.reason


def test_an_existing_ruleset_is_renamed_by_update_instead_of_being_duplicated():
    want = desired()
    assert want.ruleset is not None
    echoed = echo_ruleset(want.ruleset, ruleset_id=7)
    echoed["name"] = "main protection"
    state = observed(repo("panlabs-tech/ethitorial", rulesets=[echoed]))

    plan = planner.plan(state, want)

    assert actions_for(plan, "panlabs-tech/ethitorial") == [planner.UPDATE_RULESET]
    assert "name" in plan.items[0].reason


# --- alvo derivado da org viva ------------------------------------------------


def test_a_repo_that_appears_in_the_live_org_enters_the_plan_without_any_code_change():
    want = desired()
    raw = load_fleet_raw()
    raw["repos"].append(repo("panlabs-tech/recem-nascido"))

    plan = planner.plan(build_observed(raw), want)

    assert actions_for(plan, "panlabs-tech/recem-nascido") == [planner.CREATE_RULESET]


def test_the_whole_live_fleet_snapshot_is_covered_by_the_plan():
    want = desired()

    plan = planner.plan(fleet(), want)

    assert {item.target for item in plan} == {r.name for r in fleet().repos}
    assert planner.plan(fleet(), want) == plan


def test_the_plan_is_ordered_by_repo_name_whatever_order_the_org_listed_them_in():
    """Plano instável não é comparável nem revisável: duas leituras teriam de bater."""
    want = desired()
    scrambled = observed(
        repo("panlabs-tech/zulu"),
        repo("panlabs-tech/alfa"),
        repo("panlabs-tech/mike"),
    )

    targets = [item.target for item in planner.plan(scrambled, want)]

    assert targets == ["panlabs-tech/alfa", "panlabs-tech/mike", "panlabs-tech/zulu"]


def test_the_live_fleet_snapshot_plans_exactly_what_the_observed_state_calls_for():
    want = desired()

    plan = planner.plan(fleet(), want)

    assert actions_for(plan, "panlabs-tech/.github") == [planner.CREATE_RULESET]
    assert actions_for(plan, "panlabs-tech/skills") == [planner.CREATE_RULESET]
    assert actions_for(plan, "panlabs-tech/ethitorial") == [planner.UPDATE_RULESET]
    assert actions_for(plan, "panlabs-tech/panlabs") == [
        planner.CREATE_RULESET,
        planner.DELETE_CLASSIC_PROTECTION,
    ]


# --- configuração ainda não decidida -----------------------------------------


def test_an_undecided_desired_state_plans_nothing_at_all():
    plan = planner.plan(fleet(), Desired(ruleset=None, retire_classic_protection=None))

    assert not plan
