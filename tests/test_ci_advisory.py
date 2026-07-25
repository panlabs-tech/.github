"""A análise estática é advisory, e ficar fora do gate é decisão, não lacuna.

A regra de ruleset que exige análise de código pendura o merge por "análise em
andamento" e por "ferramenta não configurada", sem timeout: motivos que não são
alerta. A spec de Org #2 a deixou de fora de propósito, e este arquivo é onde
essa escolha fica escrita e verificada, em vez de passar por esquecimento.

O que se testa não é o CodeQL: é a fiação. Que nenhuma regra do ruleset entregue
exige a análise, e que nenhum job que publica um required check depende dela.
"""

from typing import Any

from panlabs.ci import advisory, rollup
from panlabs.ruleset.config import DEFAULT_CONFIG_PATH, load_desired
from shipped import workflow

DOTGITHUB_LANGUAGES = ("python", "actions")


def ruleset_with(*rules: dict[str, Any]) -> dict[str, Any]:
    return {"name": "panlabs", "target": "branch", "rules": list(rules)}


def requiring_checks(*contexts: str) -> dict[str, Any]:
    return {
        "type": "required_status_checks",
        "parameters": {"required_status_checks": [{"context": c} for c in contexts]},
    }


# --- nenhuma regra do ruleset entregue exige a análise -------------------------


def test_the_ruleset_shipped_in_this_repo_demands_no_code_scanning_at_all():
    """O critério da issue #15, contra o dado entregue, não contra uma cópia dele."""
    want = load_desired(DEFAULT_CONFIG_PATH)

    assert advisory.demands_code_scanning(want.ruleset) == ()


def test_no_name_in_the_shipped_check_contract_comes_from_the_analysis():
    want = load_desired(DEFAULT_CONFIG_PATH)

    assert not [c for c in want.check_contract if advisory.is_code_scanning_check(c)]


def test_a_ruleset_carrying_the_code_scanning_rule_is_caught_so_the_check_is_not_vacuous():
    """Sem este, o teste acima passaria mesmo com o detector cego."""
    reasons = advisory.demands_code_scanning(ruleset_with({"type": "code_scanning"}))

    assert len(reasons) == 1
    assert advisory.CODE_SCANNING_RULE_TYPE in reasons[0]


def test_a_required_status_check_named_after_the_analysis_is_caught_too():
    """A regra dedicada não é a única forma de pendurar o merge na análise."""
    published = "code-scanning / analyze (python)"

    reasons = advisory.demands_code_scanning(ruleset_with(requiring_checks(published)))

    assert len(reasons) == 1
    assert published in reasons[0]


def test_the_codeql_results_check_is_caught_because_it_is_the_one_that_hangs_the_merge():
    reasons = advisory.demands_code_scanning(ruleset_with(requiring_checks("CodeQL")))

    assert len(reasons) == 1


def test_the_two_ways_of_demanding_the_analysis_are_reported_as_two_reasons():
    reasons = advisory.demands_code_scanning(
        ruleset_with({"type": "code_scanning"}, requiring_checks("CodeQL"))
    )

    assert len(reasons) == 2


def test_the_required_checks_of_the_rollup_contract_are_never_read_as_the_analysis():
    """`checks` e `security` continuam exigidos: o detector não pode confundi-los."""
    reasons = advisory.demands_code_scanning(ruleset_with(requiring_checks("checks", "security")))

    assert reasons == ()


def test_an_undecided_ruleset_demands_nothing_because_it_decided_nothing():
    assert advisory.demands_code_scanning(None) == ()


def test_the_names_the_analysis_publishes_never_collide_with_the_required_contract():
    published = advisory.code_scanning_check_names(DOTGITHUB_LANGUAGES)

    assert published & rollup.required_status_names(["python"]) == frozenset()


def test_the_analysis_publishes_one_name_per_language_because_the_jobs_are_parallel():
    published = advisory.code_scanning_check_names(DOTGITHUB_LANGUAGES)

    assert published == {
        "code-scanning / analyze (python)",
        "code-scanning / analyze (actions)",
    }


def test_a_matrix_is_safe_here_precisely_because_none_of_these_names_is_required():
    """O nome de perna de matrix é o que o rollup existe para evitar em required check.

    Aqui ele é inofensivo, e é a diferença entre os dois regimes: um required
    check precisa de nome fixo; um advisory pode publicar um nome por linguagem.
    """
    one = advisory.code_scanning_check_names(["python"])
    two = advisory.code_scanning_check_names(["python", "actions"])

    assert one != two
    assert all(advisory.is_code_scanning_check(name) for name in one | two)


# --- nenhum job que publica required check depende da análise ------------------


def test_the_file_that_publishes_the_required_checks_never_calls_the_analysis():
    """Um `needs` a mais e o advisory viraria gate sem ninguém decidir isso."""
    jobs = workflow("pr-checks.yml")["jobs"]

    for name, job in jobs.items():
        assert advisory.CODE_SCANNING_WORKFLOW not in (job.get("uses") or ""), name
        assert advisory.CODE_SCANNING_JOB not in (job.get("needs") or ()), name


def test_the_analysis_lives_in_its_own_caller_so_the_separation_is_structural():
    """`.github` consome a análise por referência local, como os outros quatro."""
    job = workflow("pr-code-scanning.yml")["jobs"][advisory.CODE_SCANNING_JOB]

    assert job["uses"] == f"./.github/workflows/{advisory.CODE_SCANNING_WORKFLOW}"


def test_the_analysis_runs_on_pull_request_which_is_where_it_reports():
    triggers = workflow("pr-code-scanning.yml")["on"]

    assert "pull_request" in triggers


def test_no_job_of_the_analysis_caller_can_publish_a_required_check_name():
    """Coincidir com `checks` ou `security` faria o advisory virar gate pelo nome."""
    jobs = set(workflow("pr-code-scanning.yml")["jobs"])

    assert jobs & rollup.required_status_names([]) == set()


def test_the_analysis_asks_for_the_permission_it_needs_to_report_and_nothing_more():
    """Achado que não sobe não é reporte; escopo além disso não é advisory."""
    permissions = workflow("code-scanning.yml")["permissions"]

    assert permissions == {"contents": "read", "security-events": "write"}
