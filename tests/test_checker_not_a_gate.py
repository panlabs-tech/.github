"""O checker roda agendado, e nunca como gate de PR. Em todo repo.

A propriedade não é preferência de organização. Anatomia é propriedade do
repositório, não do diff: um gate de PR puniria um PR inocente por dívida
pré-existente, e metade dos itens (descrição, topics, wiki) nem mora no working
tree para o diff poder consertar.

"Em todo repo" é verificado em duas metades, e nenhuma delas toca a rede. A
primeira é a CI compartilhada entregue aqui, que os outros repositórios
**referenciam** em vez de copiar: se nenhum workflow daqui invoca o checker,
nenhum repo o roda por essa via, e o `.github` é o primeiro consumidor dos
próprios workflows. A segunda é o caller de cada repositório da frota, que o
retrato observado já carrega como conteúdo -- é para isso que ler conteúdo serve.

O outro lado da mesma propriedade é onde ele **de fato** roda: como passo do
heartbeat da máquina, que é o único relógio periódico que ela tem.
"""

import json
from pathlib import Path

from panlabs.checker.observe import build_observed
from panlabs.heartbeat.config import DEFAULT_CONFIG_PATH, load_desired
from panlabs.heartbeat.model import BRANCH_UP
from shipped import WORKFLOWS_DIR

FLEET = Path(__file__).parent / "fixtures" / "checker-fleet-2026-07-25.json"

CHECKER = "panlabs-checker"
STEP = "anatomy-checker"
CALLER = ".github/workflows/pr-checks.yml"


def workflow_files():
    return sorted(WORKFLOWS_DIR.glob("*.yml"))


def test_there_are_workflows_to_check_at_all():
    """Um glob vazio faria os testes abaixo passarem sem verificar coisa nenhuma."""
    assert workflow_files()


def test_no_shipped_workflow_runs_the_checker():
    for path in workflow_files():
        assert CHECKER not in path.read_text(encoding="utf-8"), path.name


def test_no_repo_of_the_fleet_runs_the_checker_in_its_pr_caller():
    """A outra metade de "em todo repo", lida do retrato observado e sem rede."""
    state = build_observed(json.loads(FLEET.read_text(encoding="utf-8")))
    callers = {repo.name: repo.content(CALLER) for repo in state.repos}
    read = {name: body for name, body in callers.items() if body is not None}

    assert read, f"nenhum caller foi lido: `{CALLER}` saiu de `config/checker.json`?"
    for name, body in read.items():
        assert CHECKER not in body, name


def test_the_checker_runs_as_a_heartbeat_step_instead():
    steps = load_desired(DEFAULT_CONFIG_PATH).steps or ()

    assert [step.name for step in steps if step.name == STEP] == [STEP]


def test_the_checker_step_lives_on_the_branch_where_the_machine_is_up():
    """Ele precisa de rede e do token já autenticado da máquina; a poda não precisa."""
    steps = load_desired(DEFAULT_CONFIG_PATH).steps or ()
    checker = next(step for step in steps if step.name == STEP)

    assert checker.branch == BRANCH_UP
    assert checker.report is not None
