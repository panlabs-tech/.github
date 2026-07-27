"""O seam compartilhado: o que um Plan garante, independentemente de quem o produziu."""

import json

import pytest

from panlabs.plan import Plan, PlanItem, Unobservable, apply, report_held


def test_item_without_reason_is_rejected_because_plan_without_reason_is_not_reviewable():
    with pytest.raises(ValueError, match="motivo"):
        PlanItem(action="create-ruleset", target="org/repo", reason="")


def test_item_without_action_or_target_is_rejected():
    with pytest.raises(ValueError, match="ação"):
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


def test_serialized_plan_carries_action_target_reason_and_the_payload_to_send():
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

    payload = json.loads(plan.to_json())

    assert payload == {
        "items": [
            {
                "action": "create-ruleset",
                "target": "panlabs-tech/skills",
                "reason": "nenhum ruleset governa a branch main",
                "payload": {"name": "main", "rules": [{"type": "deletion"}]},
                "hold": "",
            }
        ]
    }


def test_serialized_plan_keeps_accents_readable_instead_of_escaping_them():
    plan = Plan((PlanItem(action="a", target="b", reason="proteção clássica ativa"),))

    assert "proteção clássica ativa" in plan.to_json()


def test_rendered_plan_groups_items_by_target_and_names_action_and_reason():
    plan = Plan(
        (
            PlanItem(
                action="update-ruleset", target="panlabs-tech/tfbox", reason="método de merge"
            ),
            PlanItem(action="delete-classic", target="panlabs-tech/tfbox", reason="fonte dupla"),
            PlanItem(action="create-ruleset", target="panlabs-tech/skills", reason="sem ruleset"),
        )
    )

    rendered = plan.render()

    assert rendered.index("panlabs-tech/tfbox") < rendered.index("panlabs-tech/skills")
    assert rendered.count("panlabs-tech/tfbox") == 1
    assert "update-ruleset" in rendered
    assert "método de merge" in rendered
    assert "fonte dupla" in rendered


def test_rendered_empty_plan_reports_emptiness_without_claiming_convergence():
    rendered = Plan().render()

    assert "Nada a fazer" in rendered
    assert "converge" not in rendered


# --- item retido: planejado, visível, não aplicado ---------------------------


def test_a_held_item_stays_in_the_plan_to_be_read_but_is_not_applied():
    """Reter é decisão do planner. O plano continua mostrando o que não vai rodar."""
    calls: list[str] = []
    plan = Plan(
        (
            PlanItem(action="create", target="a", reason="r"),
            PlanItem(action="create", target="b", reason="r", hold="a CI de b não publica o check"),
        )
    )

    apply(plan, {"create": lambda item: calls.append(item.target)})

    assert calls == ["a"]
    assert len(plan) == 2
    assert [item.target for item in plan.applicable] == ["a"]
    assert [item.target for item in plan.held] == ["b"]


def test_a_plan_entirely_held_applies_nothing_at_all():
    calls: list[str] = []
    plan = Plan((PlanItem(action="create", target="a", reason="r", hold="adiado"),))

    apply(plan, {"create": lambda item: calls.append(item.target)})

    assert calls == []
    assert plan


def test_rendered_plan_names_what_is_held_and_why_instead_of_hiding_it():
    plan = Plan(
        (
            PlanItem(action="update-ruleset", target="org/x", reason="diverge no merge"),
            PlanItem(
                action="update-ruleset",
                target="org/y",
                reason="diverge no merge",
                hold="os checks observados são web, api",
            ),
        )
    )

    rendered = plan.render()

    assert "retido" in rendered
    assert "os checks observados são web, api" in rendered
    assert "1 retido" in rendered


def test_serialized_plan_carries_the_hold_so_a_reader_knows_what_will_not_run():
    plan = Plan((PlanItem(action="a", target="b", reason="c", hold="adiado até o retrofit"),))

    assert json.loads(plan.to_json())["items"][0]["hold"] == "adiado até o retrofit"


def test_the_held_report_carries_each_item_reason_instead_of_summarizing_them(
    capsys: pytest.CaptureFixture[str],
):
    """Um script tem quantas causas de retenção o seu domínio tiver.

    O relato tem uma forma só, e ela é alimentada pelo motivo que o planner
    escreveu no item. Resumir aqui obrigaria a escolher uma causa, e um script com
    duas passaria a nomear a errada em metade dos casos.
    """
    plan = Plan(
        (
            PlanItem(action="create", target="org/x", reason="r", hold="a CI ainda não publica"),
            PlanItem(action="observe", target="org/y", reason="r", hold="o plano da conta recusou"),
        )
    )

    report_held(plan)
    err = capsys.readouterr().err

    assert "a CI ainda não publica" in err
    assert "o plano da conta recusou" in err
    assert "org/x" in err and "org/y" in err


def test_the_held_report_says_nothing_was_applied_when_nothing_was_applicable(
    capsys: pytest.CaptureFixture[str],
):
    """Silêncio depois de `--apply` se lê como aplicação bem-sucedida."""
    plan = Plan((PlanItem(action="create", target="org/x", reason="r", hold="adiado"),))

    report_held(plan)

    assert "Nada a aplicar" in capsys.readouterr().err


def test_the_held_report_is_silent_when_there_is_nothing_held(
    capsys: pytest.CaptureFixture[str],
):
    """Um plano sem retenção não ganha parágrafo dizendo que não tem retenção."""
    report_held(Plan((PlanItem(action="create", target="org/x", reason="r"),)))

    assert capsys.readouterr().err == ""


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


# --- a outra palavra para ausência ---------------------------------------------
#
# O seam já carregava "não decidido", que é ausência no **dado**. `Unobservable` é
# ausência na **plataforma**, e as duas precisam de nomes diferentes porque levam a
# lugares opostos: nada é planejado para o que ninguém decidiu, e é planejado e
# retido o que ninguém conseguiu observar.


def test_an_unobservable_dimension_without_a_reason_is_rejected():
    """Mesma regra do item de plano: retenção sem motivo escrito não é revisável."""
    with pytest.raises(ValueError, match="motivo"):
        Unobservable("")


def test_an_unobservable_dimension_is_not_a_boolean_in_disguise():
    """O tipo é o guarda: `False` e "não consegui ler" não podem se confundir.

    Um `bool | None` faria os dois caberem no mesmo `if not`, e o primeiro leitor
    distraído transformaria "a plataforma não mostrou" em "está desligado", que é
    exatamente a mentira que a doutrina deste repo proíbe.
    """
    unobservable = Unobservable("o GitHub recusou a leitura")

    assert not isinstance(unobservable, bool)
    assert unobservable.reason == "o GitHub recusou a leitura"
