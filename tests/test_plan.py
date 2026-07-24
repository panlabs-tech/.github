"""O seam compartilhado: o que um Plan garante, independentemente de quem o produziu."""

import json

import pytest

from panlabs.plan import Plan, PlanItem, apply


def test_item_without_reason_is_rejected_because_plan_without_reason_is_not_reviewable():
    with pytest.raises(ValueError, match="motivo"):
        PlanItem(action="create-ruleset", target="org/repo", reason="")


def test_item_without_action_or_target_is_rejected():
    with pytest.raises(ValueError, match="acao"):
        PlanItem(action="", target="org/repo", reason="divergiu")

    with pytest.raises(ValueError, match="alvo"):
        PlanItem(action="create-ruleset", target="", reason="divergiu")


def test_empty_plan_is_falsy_and_a_populated_one_is_truthy():
    empty = Plan()
    populated = Plan((PlanItem(action="a", target="b", reason="c"),))

    assert not empty
    assert len(empty) == 0
    assert populated
    assert len(populated) == 1


def test_plan_round_trips_through_json_preserving_every_field():
    plan = Plan(
        (
            PlanItem(
                action="create-ruleset",
                target="panlabs-tech/skills",
                reason="nenhum ruleset governa a branch main",
                payload={"name": "main", "rules": [{"type": "deletion"}]},
            ),
        )
    )

    restored = Plan.from_dict(json.loads(plan.to_json()))

    assert restored == plan


def test_rendered_plan_groups_items_by_target_and_names_action_and_reason():
    plan = Plan(
        (
            PlanItem(
                action="update-ruleset", target="panlabs-tech/tfbox", reason="metodo de merge"
            ),
            PlanItem(action="delete-classic", target="panlabs-tech/tfbox", reason="fonte dupla"),
            PlanItem(action="create-ruleset", target="panlabs-tech/skills", reason="sem ruleset"),
        )
    )

    rendered = plan.render()

    assert rendered.index("panlabs-tech/tfbox") < rendered.index("panlabs-tech/skills")
    assert rendered.count("panlabs-tech/tfbox") == 1
    assert "update-ruleset" in rendered
    assert "metodo de merge" in rendered
    assert "fonte dupla" in rendered


def test_rendered_empty_plan_reports_emptiness_without_claiming_convergence():
    rendered = Plan().render()

    assert "Nada a fazer" in rendered
    assert "converge" not in rendered


def test_apply_runs_the_effect_registered_for_each_action_in_plan_order():
    calls: list[tuple[str, str]] = []
    plan = Plan(
        (
            PlanItem(action="create", target="a", reason="r"),
            PlanItem(action="delete", target="b", reason="r"),
            PlanItem(action="create", target="c", reason="r"),
        )
    )

    apply(
        plan,
        {
            "create": lambda item: calls.append(("create", item.target)),
            "delete": lambda item: calls.append(("delete", item.target)),
        },
    )

    assert calls == [("create", "a"), ("delete", "b"), ("create", "c")]


def test_apply_of_an_empty_plan_touches_nothing():
    calls: list[str] = []

    apply(Plan(), {"create": lambda item: calls.append(item.target)})

    assert calls == []


def test_apply_raises_when_no_effect_is_registered_for_an_action():
    plan = Plan((PlanItem(action="unknown", target="a", reason="r"),))

    with pytest.raises(KeyError, match="unknown"):
        apply(plan, {})
