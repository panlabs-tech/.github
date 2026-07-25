"""O checker roda agendado, e nunca como gate de PR. Em todo repo.

A propriedade não é preferência de organização. Anatomia é propriedade do
repositório, não do diff: um gate de PR puniria um PR inocente por dívida
pré-existente, e metade dos itens (descrição, topics, wiki) nem mora no working
tree para o diff poder consertar.

"Em todo repo" é verificável daqui, e não por varredura da frota: os repositórios
da org **referenciam** a CI compartilhada deste repo em vez de copiá-la. Se
nenhum workflow entregue aqui invoca o checker, nenhum repo o roda por essa via,
e o `.github` é o primeiro consumidor dos próprios workflows.

O outro lado da mesma propriedade é onde ele **de fato** roda: como passo do
heartbeat da máquina, que é o único relógio periódico que ela tem.
"""

from panlabs.heartbeat.config import DEFAULT_CONFIG_PATH, load_desired
from panlabs.heartbeat.model import BRANCH_UP
from shipped import WORKFLOWS_DIR

CHECKER = "panlabs-checker"
STEP = "anatomy-checker"


def workflow_files():
    return sorted(WORKFLOWS_DIR.glob("*.yml"))


def test_there_are_workflows_to_check_at_all():
    """Um glob vazio faria os testes abaixo passarem sem verificar coisa nenhuma."""
    assert workflow_files()


def test_no_shipped_workflow_runs_the_checker():
    for path in workflow_files():
        assert CHECKER not in path.read_text(encoding="utf-8"), path.name


def test_the_checker_runs_as_a_heartbeat_step_instead():
    steps = load_desired(DEFAULT_CONFIG_PATH).steps or ()

    assert [step.name for step in steps if step.name == STEP] == [STEP]


def test_the_checker_step_lives_on_the_branch_where_the_machine_is_up():
    """Ele precisa de rede e do token já autenticado da máquina; a poda não precisa."""
    steps = load_desired(DEFAULT_CONFIG_PATH).steps or ()
    checker = next(step for step in steps if step.name == STEP)

    assert checker.branch == BRANCH_UP
    assert checker.report is not None
