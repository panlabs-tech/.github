"""Dependabot com auto-merge no verde, e major sempre esperando olho humano.

Sem auto-merge, o aproveitamento medido na própria org foi de 17%: 46 PRs, 8
mergeados, 28 fechados, 10 parados. Com ele, um bump minor ou patch aterrissa
sozinho assim que os checks ficam verdes, e um bump major não aterrissa sozinho
nunca, não importa o estado dos checks.

O que se testa é a decisão e a configuração entregue, não o Dependabot: se a
plataforma abre o PR e se o `--auto` do `gh` espera o verde são fatos dela.
"""

from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from panlabs.ci import dependabot
from panlabs.ruleset.config import DEFAULT_CONFIG_PATH, load_desired
from shipped import dependabot_config, workflow

BOT = dependabot.DEPENDABOT_ACTOR

Updates = Iterable[Mapping[str, Any]]


def shipped_updates() -> list[dict[str, Any]]:
    return dependabot_config()["updates"]


def ecosystems_of(updates: Updates) -> set[str]:
    return {ecosystem for ecosystem, _ in dependabot.update_targets(updates)}


def groups_of(updates: Updates) -> Iterator[tuple[str, Mapping[str, Any]]]:
    for update in updates:
        yield from (update.get("groups") or {}).items()


# --- minor e patch mergeiam sozinhos; major nunca ------------------------------


def test_a_patch_bump_from_dependabot_merges_by_itself():
    assert dependabot.automerges(BOT, dependabot.SEMVER_PATCH)


def test_a_minor_bump_from_dependabot_merges_by_itself():
    assert dependabot.automerges(BOT, dependabot.SEMVER_MINOR)


def test_a_major_bump_never_merges_by_itself_no_matter_what_the_checks_say():
    """Quebra de contrato exige olho humano: é o critério da spec, não uma folga."""
    assert not dependabot.automerges(BOT, dependabot.SEMVER_MAJOR)


def test_an_update_type_nobody_taught_the_rule_about_never_merges_by_itself():
    """Default fechado: o que não foi decidido espera humano, não vira minor por descuido."""
    assert not dependabot.automerges(BOT, "version-update:semver-preview")


def test_an_empty_update_type_never_merges_by_itself():
    """É o que sai quando a leitura de metadados não encontrou bump nenhum."""
    assert not dependabot.automerges(BOT, "")


def test_a_patch_bump_opened_by_anyone_else_never_merges_by_itself():
    """A automação é do Dependabot; PR humano continua passando pela esteira inteira."""
    assert not dependabot.automerges("paninit", dependabot.SEMVER_PATCH)


def test_the_merge_method_asked_for_is_the_only_one_the_gate_allows():
    """Pedir merge-commit ou rebase seria recusado: o ruleset só permite squash."""
    want = load_desired(DEFAULT_CONFIG_PATH)
    assert want.ruleset is not None
    pull_request = next(r for r in want.ruleset["rules"] if r["type"] == "pull_request")

    assert pull_request["parameters"]["allowed_merge_methods"] == [dependabot.MERGE_METHOD]


# --- a configuração declara cada alvo uma vez só -------------------------------


def test_two_entries_for_the_same_ecosystem_and_directory_are_reported_as_duplicate():
    updates = [
        {"package-ecosystem": "uv", "directory": "/"},
        {"package-ecosystem": "uv", "directory": "/"},
    ]

    assert dependabot.duplicate_targets(updates) == (("uv", "/"),)


def test_the_same_ecosystem_in_two_directories_is_not_duplicate():
    updates = [
        {"package-ecosystem": "uv", "directory": "/"},
        {"package-ecosystem": "uv", "directory": "/apps/api"},
    ]

    assert dependabot.duplicate_targets(updates) == ()


def test_two_ecosystems_in_the_same_directory_are_not_duplicate():
    updates = [
        {"package-ecosystem": "uv", "directory": "/"},
        {"package-ecosystem": "github-actions", "directory": "/"},
    ]

    assert dependabot.duplicate_targets(updates) == ()


def test_the_plural_form_declares_one_target_per_directory():
    updates = [{"package-ecosystem": "uv", "directories": ["/", "/apps/api"]}]

    assert dependabot.update_targets(updates) == (("uv", "/"), ("uv", "/apps/api"))


def test_the_two_ways_of_naming_a_directory_collide_like_any_other_duplicate():
    """É por aqui que uma duplicata entraria sem ninguém ver: formas diferentes, alvo igual."""
    updates = [
        {"package-ecosystem": "uv", "directory": "/"},
        {"package-ecosystem": "uv", "directories": ["/"]},
    ]

    assert dependabot.duplicate_targets(updates) == (("uv", "/"),)


def test_an_entry_that_names_no_directory_lands_on_the_root_like_dependabot_reads_it():
    updates = [{"package-ecosystem": "uv"}]

    assert dependabot.update_targets(updates) == (("uv", "/"),)


# --- a configuração entregue por este repo ------------------------------------


def test_the_shipped_config_declares_no_target_twice():
    """Rodar a configuração de novo não abre um segundo PR para o mesmo alvo."""
    assert dependabot.duplicate_targets(shipped_updates()) == ()


def test_the_shipped_config_covers_the_actions_ecosystem_that_keeps_the_sha_pins_fresh():
    """O pinning por SHA dos workflows compartilhados depende deste ecossistema existir."""
    assert "github-actions" in ecosystems_of(shipped_updates())


def test_the_shipped_config_covers_uv_and_not_pip_because_pip_would_leave_the_lock_behind():
    """`uv sync --frozen` reprovaria um bump que mexeu no pyproject sem refazer o lock."""
    ecosystems = ecosystems_of(shipped_updates())

    assert "uv" in ecosystems
    assert "pip" not in ecosystems


def test_every_group_in_the_shipped_config_says_which_update_types_it_carries():
    """Grupo sem `update-types` varre major junto e leva o auto-merge do resto embora."""
    for name, group in groups_of(shipped_updates()):
        assert group.get("update-types"), name


def test_no_group_in_the_shipped_config_carries_major():
    """Major agrupado com minor prende o grupo inteiro esperando humano."""
    for name, group in groups_of(shipped_updates()):
        assert "major" not in group["update-types"], name


def test_every_update_type_the_shipped_groups_carry_is_one_that_auto_merges():
    """O grupo e a regra de auto-merge são a mesma decisão, vista de dois lados."""
    for name, group in groups_of(shipped_updates()):
        for update_type in group["update-types"]:
            assert dependabot.automerges(BOT, f"version-update:semver-{update_type}"), name


# --- os checks precisam existir para o auto-merge ter o que esperar ------------


def test_the_branches_dependabot_pushes_reach_the_workflow_that_publishes_the_checks():
    """A falha mais silenciosa deste desenho: sem isso, o auto-merge espera para sempre."""
    branches = workflow("pr-checks.yml")["on"]["push"]["branches"]

    assert dependabot.covers_dependabot_branches(branches)


def test_a_branch_filter_list_without_dependabot_is_reported_as_not_covering_it():
    assert not dependabot.covers_dependabot_branches(["feat/**", "worktree-**"])


def test_the_pr_that_the_esteira_opens_is_not_opened_again_for_a_dependabot_branch():
    """O Dependabot já abre o próprio PR; `open-pr` rodar ali seria ruído ou corrida."""
    open_pr = workflow("pr-checks.yml")["jobs"]["open-pr"]

    assert BOT in open_pr["if"]


def test_the_auto_merge_is_consumed_by_local_reference_like_every_other_workflow():
    job = workflow("pr-dependabot-auto-merge.yml")["jobs"][dependabot.AUTO_MERGE_JOB]

    assert job["uses"] == f"./.github/workflows/{dependabot.AUTO_MERGE_WORKFLOW}"


def test_the_auto_merge_asks_for_the_permission_it_needs_to_merge_and_nothing_more():
    permissions = workflow(dependabot.AUTO_MERGE_WORKFLOW)["permissions"]

    assert permissions == {"contents": "write", "pull-requests": "write"}
