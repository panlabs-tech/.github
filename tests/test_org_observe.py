"""A observação: um campo que a API não devolveu nunca vira um fato sobre a org.

Metade destas dimensões só é legível por quem administra a org, e o GitHub
responde a um token curto **omitindo** os campos, não negando a resposta. Se a
omissão virasse `False`, um token sem escopo diria "a esteira está desligada" e
"o wiki está conforme" com a mesma cara de quem observou. Cada campo ausente é
erro alto, e é isso que estes testes prendem.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from panlabs.org.observe import build_observed

FIXTURES = Path(__file__).parent / "fixtures"
FLEET = FIXTURES / "org-fleet-2026-07-24.json"


def fleet_raw() -> dict[str, Any]:
    return json.loads(FLEET.read_text(encoding="utf-8"))


def test_the_live_snapshot_builds_the_state_the_planner_reads():
    observed = build_observed(fleet_raw())

    assert observed.org.login == "panlabs-tech"
    assert observed.org.actions.can_approve_pull_requests is True
    assert len(observed.repos) == 7


ADMIN_ONLY_ORG_FIELDS = ["two_factor_requirement_enabled"]
ADMIN_ONLY_REPO_FIELDS = [
    "security_and_analysis",
    "vulnerability_alerts",
    "automated_security_fixes",
]


@pytest.mark.parametrize("field", ADMIN_ONLY_ORG_FIELDS)
def test_an_org_field_only_an_admin_sees_is_an_error_when_absent(field: str):
    raw = fleet_raw()
    del raw["org"][field]

    with pytest.raises(ValueError, match="admin:org"):
        build_observed(raw)


@pytest.mark.parametrize("field", ADMIN_ONLY_REPO_FIELDS)
def test_a_repo_field_only_an_admin_sees_is_an_error_when_absent(field: str):
    raw = fleet_raw()
    del raw["repos"][0][field]

    with pytest.raises(ValueError, match="admin:org"):
        build_observed(raw)


def test_the_actions_policy_block_is_never_assumed():
    """Sem ela, "a esteira caiu" seria afirmação de quem não observou nada."""
    raw = fleet_raw()
    del raw["actions_workflow_permissions"]

    with pytest.raises(ValueError, match="can_approve_pull_request_reviews"):
        build_observed(raw)


def test_the_default_workflow_permission_is_read_from_the_org_not_invented():
    """Ela não é dimensão desta configuração, mas viaja no corpo que a aplica."""
    raw = fleet_raw()
    raw["actions_workflow_permissions"]["default_workflow_permissions"] = "write"

    assert build_observed(raw).org.actions.default_workflow_permissions == "write"


def test_an_absent_pin_list_is_an_error_instead_of_an_empty_showcase():
    raw = fleet_raw()
    del raw["pinned_repos"]

    with pytest.raises(ValueError, match="pinned_repos"):
        build_observed(raw)


def test_an_absent_wiki_flag_is_an_error_instead_of_silent_conformance():
    raw = fleet_raw()
    del raw["repos"][0]["has_wiki"]

    with pytest.raises(ValueError, match="has_wiki"):
        build_observed(raw)


def test_a_repo_without_description_or_topics_is_observed_as_such_not_rejected():
    """Ausência de vitrine é fato observável, e o planner é quem decide o que fazer."""
    raw = fleet_raw()
    repo = raw["repos"][0]
    repo["description"] = None
    repo["topics"] = []

    observed = build_observed(raw).repos[0]

    assert observed.description is None
    assert observed.topics == ()
