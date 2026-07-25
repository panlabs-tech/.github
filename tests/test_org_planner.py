"""O planner de org e repo: qual divergência vira qual item de plano.

O teste que mais importa aqui é o de idempotência, dimensão por dimensão: é ele
que permite rodar o comando sem medo, e é a razão de o comando poder ser usado
como *verificação* de invariante e não só como aplicador.

O planner é puro. Nada aqui toca rede, token ou disco além das fixtures.
"""

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from panlabs.org import planner
from panlabs.org.config import Desired, load_desired
from panlabs.org.model import Observed
from panlabs.org.observe import build_observed
from panlabs.plan import Plan, PlanItem

FIXTURES = Path(__file__).parent / "fixtures"
FLEET = FIXTURES / "org-fleet-2026-07-24.json"
DESIRED = FIXTURES / "desired-org.json"

ORG = "panlabs-tech"


def desired() -> Desired:
    return load_desired(DESIRED)


def items_for(plan: Plan, target: str) -> list[PlanItem]:
    return [item for item in plan if item.target == target]


def actions_for(plan: Plan, target: str) -> list[str]:
    return [item.action for item in items_for(plan, target)]


# --- um estado observado que converge com o desejado --------------------------
#
# Construído *a partir* do desejado, e não copiado à mão: um estado conforme
# escrito à mão envelheceria em silêncio na primeira mudança do dado, e o teste
# de idempotência passaria a provar outra coisa.


def conforming_repo(name: str, want: Desired) -> dict[str, Any]:
    """O retrato cru de um repo que já converge com o desejado, em tudo."""
    full_name = f"{ORG}/{name}"
    wiki = want.wiki or {}
    excepted = full_name in (wiki.get("exceptions") or ())
    return {
        "full_name": full_name,
        "description": (want.repo_descriptions or {}).get(full_name, "descrição qualquer"),
        "topics": list((want.repo_topics or {}).get(full_name, ["qualquer"])),
        "has_wiki": True if excepted else bool(wiki.get("enabled")),
        "security_and_analysis": {
            "secret_scanning": {"status": _status(want.secret_scanning)},
            "secret_scanning_push_protection": {"status": _status(want.push_protection)},
        },
        "vulnerability_alerts": bool(want.dependabot_alerts),
        "automated_security_fixes": {
            "enabled": bool(want.dependabot_security_updates),
            "paused": False,
        },
    }


def _status(enabled: bool | None) -> str:
    return "enabled" if enabled else "disabled"


def conforming_org(want: Desired) -> dict[str, Any]:
    org: dict[str, Any] = {
        "login": ORG,
        "description": want.org_description,
        "two_factor_requirement_enabled": bool(want.two_factor_requirement),
    }
    org.update(want.new_repo_security_defaults or {})
    return org


def conforming_raw(want: Desired, *repo_names: str) -> dict[str, Any]:
    return {
        "org": conforming_org(want),
        "actions_workflow_permissions": {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": bool(want.actions_can_approve_pull_requests),
        },
        "pinned_repos": list(want.pinned_repos or ()),
        "repos": [conforming_repo(name, want) for name in repo_names],
    }


def conforming(want: Desired, *repo_names: str) -> Observed:
    return build_observed(conforming_raw(want, *repo_names))


# --- idempotência: o teste mais importante desta issue ------------------------


def test_a_fleet_that_already_converges_yields_an_empty_plan():
    want = desired()

    plan = planner.plan(conforming(want, "alfa", "bravo", "tfbox"), want)

    assert not plan
    assert plan.render().startswith("Nada a fazer")


def test_the_wiki_exception_repo_converges_with_its_wiki_still_on():
    """A exceção é dado declarado: o repo do wiki de release não vira divergência."""
    want = desired()
    assert want.wiki is not None
    exception = str(want.wiki["exceptions"][0])

    raw = conforming_raw(want, exception.removeprefix(f"{ORG}/"))
    assert raw["repos"][0]["has_wiki"] is True

    assert not planner.plan(build_observed(raw), want)


# --- cada dimensão diverge sozinha -------------------------------------------
#
# Um repo (ou uma org) com só uma dimensão fora do padrão produz exatamente um
# item, e o motivo nomeia qual. É o que permite ler o plano e saber o que caiu
# sem abrir o código.


ORG_BREAKAGES: list[tuple[str, Callable[[dict[str, Any]], None], str, str]] = [
    (
        "política de Actions",
        lambda raw: raw["actions_workflow_permissions"].update(
            {"can_approve_pull_request_reviews": False}
        ),
        planner.SET_ACTIONS_PR_POLICY,
        "esteira",
    ),
    (
        "defaults de repo novo",
        lambda raw: raw["org"].update({"secret_scanning_enabled_for_new_repositories": False}),
        planner.SET_ORG_SECURITY_DEFAULTS,
        "secret_scanning_enabled_for_new_repositories",
    ),
    (
        "2FA",
        lambda raw: raw["org"].update({"two_factor_requirement_enabled": False}),
        planner.SET_TWO_FACTOR_REQUIREMENT,
        "2FA",
    ),
    (
        "descrição da org",
        lambda raw: raw["org"].update({"description": "dados e analytics que ninguém sustenta"}),
        planner.SET_ORG_DESCRIPTION,
        "descrição",
    ),
    (
        "pins",
        lambda raw: raw.update({"pinned_repos": [f"{ORG}/tfbox"]}),
        planner.SET_PINNED_REPOS,
        "fixados",
    ),
]


@pytest.mark.parametrize(
    ("dimension", "mutate", "action", "reason_names"),
    ORG_BREAKAGES,
    ids=[case[0] for case in ORG_BREAKAGES],
)
def test_a_single_broken_org_dimension_yields_exactly_one_item_naming_it(
    dimension: str,
    mutate: Callable[[dict[str, Any]], None],
    action: str,
    reason_names: str,
):
    want = desired()
    raw = conforming_raw(want, "alfa")
    mutate(raw)

    plan = planner.plan(build_observed(raw), want)

    assert len(plan) == 1, f"{dimension} deveria produzir um item só"
    assert plan.items[0].action == action
    assert plan.items[0].target == ORG
    assert reason_names in plan.items[0].reason


REPO_BREAKAGES: list[tuple[str, Callable[[dict[str, Any]], None], str, str]] = [
    (
        "secret scanning",
        lambda repo: repo["security_and_analysis"]["secret_scanning"].update(
            {"status": "disabled"}
        ),
        planner.SET_SECRET_SCANNING,
        "secret scanning",
    ),
    (
        "push protection",
        lambda repo: repo["security_and_analysis"]["secret_scanning_push_protection"].update(
            {"status": "disabled"}
        ),
        planner.SET_PUSH_PROTECTION,
        "push protection",
    ),
    (
        "dependabot alerts",
        lambda repo: repo.update({"vulnerability_alerts": False}),
        planner.SET_DEPENDABOT_ALERTS,
        "dependabot alerts",
    ),
    (
        "dependabot security updates",
        lambda repo: repo["automated_security_fixes"].update({"enabled": False}),
        planner.SET_DEPENDABOT_SECURITY_UPDATES,
        "dependabot security updates",
    ),
    (
        "descrição do repo",
        lambda repo: repo.update({"description": "outra coisa"}),
        planner.SET_REPO_DESCRIPTION,
        "descrição",
    ),
    (
        "topics",
        lambda repo: repo.update({"topics": ["blog", "learning"]}),
        planner.SET_REPO_TOPICS,
        "topics",
    ),
    (
        "wiki",
        lambda repo: repo.update({"has_wiki": True}),
        planner.SET_WIKI,
        "wiki",
    ),
]


@pytest.mark.parametrize(
    ("dimension", "mutate", "action", "reason_names"),
    REPO_BREAKAGES,
    ids=[case[0] for case in REPO_BREAKAGES],
)
def test_a_single_broken_repo_dimension_yields_exactly_one_item_naming_it(
    dimension: str,
    mutate: Callable[[dict[str, Any]], None],
    action: str,
    reason_names: str,
):
    want = desired()
    raw = conforming_raw(want, "ethitorial")
    mutate(raw["repos"][0])

    plan = planner.plan(build_observed(raw), want)

    assert len(plan) == 1, f"{dimension} deveria produzir um item só"
    assert plan.items[0].action == action
    assert plan.items[0].target == f"{ORG}/ethitorial"
    assert reason_names in plan.items[0].reason


def test_the_dimensions_without_an_api_are_planned_as_held_not_as_appliable():
    """Sem chamada que as realize, elas nascem retidas, com o motivo escrito."""
    want = desired()
    raw = conforming_raw(want, "recem-nascido")
    raw["org"]["two_factor_requirement_enabled"] = False
    raw["pinned_repos"] = []
    raw["repos"][0]["description"] = None
    raw["repos"][0]["topics"] = []

    plan = planner.plan(build_observed(raw), want)

    assert {item.action for item in plan.held} == planner.ALWAYS_HELD
    assert plan.applicable == ()
    assert all(item.hold for item in plan.held)


def test_a_held_item_carries_no_payload_because_no_effect_will_read_it():
    want = desired()
    raw = conforming_raw(want, "alfa")
    raw["pinned_repos"] = []

    item = planner.plan(build_observed(raw), want).items[0]

    assert item.action == planner.SET_PINNED_REPOS
    assert item.payload == {}
    assert "GraphQL" in item.hold


# --- P0: a esteira vem primeiro ----------------------------------------------


def test_the_actions_policy_is_the_first_item_of_the_plan():
    """Aplicar o plano religa a esteira antes de mexer em qualquer outra coisa."""
    want = desired()
    raw = conforming_raw(want, "alfa", "bravo")
    raw["actions_workflow_permissions"]["can_approve_pull_request_reviews"] = False
    raw["org"]["description"] = "errada"
    raw["repos"][0]["has_wiki"] = True

    plan = planner.plan(build_observed(raw), want)

    assert len(plan) > 1
    assert plan.items[0].action == planner.SET_ACTIONS_PR_POLICY


def test_the_actions_policy_item_preserves_the_permission_it_does_not_govern():
    """O corpo do PUT carrega os dois campos: enviar um só zeraria o outro."""
    want = desired()
    raw = conforming_raw(want, "alfa")
    raw["actions_workflow_permissions"] = {
        "default_workflow_permissions": "write",
        "can_approve_pull_request_reviews": False,
    }

    item = planner.plan(build_observed(raw), want).items[0]

    assert item.payload["body"] == {
        "default_workflow_permissions": "write",
        "can_approve_pull_request_reviews": True,
    }


# --- o que o applier precisa carregar ----------------------------------------


def test_the_secret_scanning_item_carries_the_exact_body_the_api_expects():
    want = desired()
    raw = conforming_raw(want, "alfa")
    raw["repos"][0]["security_and_analysis"]["secret_scanning"]["status"] = "disabled"

    item = planner.plan(build_observed(raw), want).items[0]

    assert item.payload["body"] == {
        "security_and_analysis": {"secret_scanning": {"status": "enabled"}}
    }


def test_the_dependabot_items_carry_the_http_method_so_the_applier_decides_nothing():
    """Ligar é PUT e desligar é DELETE: quem escolhe é o planner, não o efeito."""
    want = desired()
    raw = conforming_raw(want, "alfa")
    raw["repos"][0]["vulnerability_alerts"] = False

    item = planner.plan(build_observed(raw), want).items[0]

    assert item.payload["method"] == "PUT"


def test_turning_a_dimension_off_by_data_produces_the_opposite_call():
    """`false` no dado é decisão, e o plano a serve sem `if` no applier."""
    want = Desired(dependabot_alerts=False)
    raw = {
        "org": {"login": ORG, "two_factor_requirement_enabled": True},
        "actions_workflow_permissions": {
            "default_workflow_permissions": "read",
            "can_approve_pull_request_reviews": True,
        },
        "pinned_repos": [],
        "repos": [conforming_repo("alfa", Desired(dependabot_alerts=True))],
    }

    item = planner.plan(build_observed(raw), want).items[0]

    assert item.action == planner.SET_DEPENDABOT_ALERTS
    assert item.payload["method"] == "DELETE"


def test_the_topics_item_carries_the_whole_desired_list_not_only_the_difference():
    want = desired()
    raw = conforming_raw(want, "ethitorial")
    raw["repos"][0]["topics"] = ["blog", "learning"]

    item = planner.plan(build_observed(raw), want).items[0]

    assert want.repo_topics is not None
    assert item.payload["body"]["names"] == list(want.repo_topics[f"{ORG}/ethitorial"])


def test_topics_are_compared_as_a_set_because_the_api_reorders_them():
    want = desired()
    assert want.repo_topics is not None
    raw = conforming_raw(want, "ethitorial")
    raw["repos"][0]["topics"] = list(reversed(want.repo_topics[f"{ORG}/ethitorial"]))

    assert not planner.plan(build_observed(raw), want)


# --- ordem dentro do repo: uma dimensão depende da outra ---------------------


def test_secret_scanning_is_planned_before_push_protection_that_depends_on_it():
    want = desired()
    raw = conforming_raw(want, "alfa")
    raw["repos"][0]["security_and_analysis"] = {
        "secret_scanning": {"status": "disabled"},
        "secret_scanning_push_protection": {"status": "disabled"},
    }

    actions = actions_for(planner.plan(build_observed(raw), want), f"{ORG}/alfa")

    assert actions == [planner.SET_SECRET_SCANNING, planner.SET_PUSH_PROTECTION]


def test_dependabot_alerts_are_planned_before_the_security_updates_that_depend_on_them():
    want = desired()
    raw = conforming_raw(want, "alfa")
    raw["repos"][0]["vulnerability_alerts"] = False
    raw["repos"][0]["automated_security_fixes"]["enabled"] = False

    actions = actions_for(planner.plan(build_observed(raw), want), f"{ORG}/alfa")

    assert actions == [planner.SET_DEPENDABOT_ALERTS, planner.SET_DEPENDABOT_SECURITY_UPDATES]


# --- alvo derivado da org viva -----------------------------------------------


def test_a_repo_that_appears_in_the_live_org_enters_the_plan_without_any_code_change():
    want = desired()
    raw = json.loads(FLEET.read_text(encoding="utf-8"))
    raw["repos"].append(
        {
            "full_name": f"{ORG}/recem-nascido",
            "description": None,
            "topics": [],
            "has_wiki": True,
            "security_and_analysis": {
                "secret_scanning": {"status": "disabled"},
                "secret_scanning_push_protection": {"status": "disabled"},
            },
            "vulnerability_alerts": False,
            "automated_security_fixes": {"enabled": False, "paused": False},
        }
    )

    actions = actions_for(planner.plan(build_observed(raw), want), f"{ORG}/recem-nascido")

    assert actions == [
        planner.SET_SECRET_SCANNING,
        planner.SET_PUSH_PROTECTION,
        planner.SET_DEPENDABOT_ALERTS,
        planner.SET_DEPENDABOT_SECURITY_UPDATES,
        planner.DECLARE_REPO_DESCRIPTION,
        planner.DECLARE_REPO_TOPICS,
        planner.SET_WIKI,
    ]


def test_a_repo_with_no_declared_text_but_a_description_of_its_own_is_left_alone():
    """O dado governa o texto onde ele existe; onde não existe, só cobra que exista."""
    want = desired()
    raw = conforming_raw(want, "recem-nascido")
    raw["repos"][0]["description"] = "uma descrição que ninguém declarou"
    raw["repos"][0]["topics"] = ["python"]

    assert not planner.plan(build_observed(raw), want)


def test_the_plan_is_ordered_by_repo_name_whatever_order_the_org_listed_them_in():
    want = desired()
    raw = conforming_raw(want, "zulu", "alfa", "mike")
    for repo in raw["repos"]:
        repo["has_wiki"] = True

    targets = [item.target for item in planner.plan(build_observed(raw), want)]

    assert targets == [f"{ORG}/alfa", f"{ORG}/mike", f"{ORG}/zulu"]


def test_the_live_fleet_snapshot_plans_exactly_what_the_observed_state_calls_for():
    """O retrato de 2026-07-24: a esteira já religada, o resto por converger."""
    want = desired()
    fleet = build_observed(json.loads(FLEET.read_text(encoding="utf-8")))

    plan = planner.plan(fleet, want)

    assert planner.SET_ACTIONS_PR_POLICY not in [item.action for item in plan]
    assert planner.SET_TWO_FACTOR_REQUIREMENT in actions_for(plan, ORG)
    assert planner.SET_WIKI not in actions_for(plan, f"{ORG}/tfbox")
    assert planner.SET_REPO_TOPICS in actions_for(plan, f"{ORG}/ethitorial")
    assert planner.plan(fleet, want) == plan


def test_the_content_axis_topics_of_ethitorial_are_planned_as_a_divergence_to_correct():
    """O eixo é stack: `blog` e `learning` descrevem conteúdo, e saem."""
    want = desired()
    fleet = build_observed(json.loads(FLEET.read_text(encoding="utf-8")))

    item = next(
        item
        for item in items_for(planner.plan(fleet, want), f"{ORG}/ethitorial")
        if item.action == planner.SET_REPO_TOPICS
    )

    assert "blog" in item.reason
    assert "learning" in item.reason


# --- configuração ainda não decidida -----------------------------------------


def test_an_undecided_desired_state_plans_nothing_at_all():
    fleet = build_observed(json.loads(FLEET.read_text(encoding="utf-8")))

    assert not planner.plan(fleet, Desired())


def test_an_undecided_wiki_dimension_leaves_every_wiki_alone():
    want = desired()
    raw = conforming_raw(want, "alfa")
    raw["repos"][0]["has_wiki"] = True

    assert not planner.plan(build_observed(raw), replace(want, wiki=None))
