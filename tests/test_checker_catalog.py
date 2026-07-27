"""O catálogo cheio: cada item no eixo certo, e cada critério da #28 com teste.

Os testes de endereço guardam a propriedade estrutural: um item de escopo stack
morando no módulo de org mentiria sobre o eixo em que foi avaliado, e é o escopo
que permite auditar o próprio checker.

Os demais são os critérios de aceitação do catálogo cheio, um a um. Cada um parte
de um repositório **conforme** (`tests/anatomy.py`) e tira exatamente uma peça: o
que o teste mostra é a diferença, e não o estado todo.
"""

import re
from pathlib import Path
from typing import Any

from anatomy import conformant, observed, without
from panlabs.checker import planner
from panlabs.checker.catalog import build, item, load_catalog, org, stack, tipo
from panlabs.checker.config import VALID_TYPES, Anatomy, load_anatomy, load_repo_types
from panlabs.org.config import Desired, load_desired
from panlabs.plan import PlanItem

CATALOG = load_catalog()
ANATOMY_DOC = Path(__file__).resolve().parents[1] / "ANATOMY.md"


def rows(*repos: dict[str, Any]) -> list[str]:
    """Os ids que o catálogo acusa contra aqueles repositórios, em ordem."""
    return [row.action for row in planner.plan(observed(*repos), CATALOG)]


def row_for(action: str, *repos: dict[str, Any]) -> PlanItem:
    return next(row for row in planner.plan(observed(*repos), CATALOG) if row.action == action)


# --- o endereço carrega o eixo -------------------------------------------------


def test_the_catalog_is_the_three_axis_modules_concatenated_in_order():
    """Pelos ids: um item carrega closures, e duas construções nunca são iguais."""
    anatomy, desired = load_anatomy(), load_desired()
    eixos = org.items(anatomy, desired) + stack.items(anatomy) + tipo.items(anatomy)

    assert [i.id for i in build(anatomy, desired)] == [i.id for i in eixos]


def test_every_item_in_the_org_module_is_scoped_to_the_org_axis():
    assert {i.scope.kind for i in org.items(load_anatomy(), load_desired())} == {"org"}


def test_every_item_in_the_stack_module_is_scoped_to_a_named_surface():
    items = stack.items(load_anatomy())
    assert {i.scope.kind for i in items} == {"stack"}
    assert all(i.scope.value for i in items)


def test_every_item_in_the_type_module_is_scoped_to_a_named_type():
    items = tipo.items(load_anatomy())
    assert {i.scope.kind for i in items} == {"tipo"}
    assert all(i.scope.value for i in items)


def test_no_item_id_is_declared_twice_across_the_axes():
    """O id é o que aparece na matriz: dois itens homônimos seriam indistinguíveis."""
    ids = [i.id for i in CATALOG]

    assert len(ids) == len(set(ids))


def test_nothing_written_in_the_document_is_left_without_a_verdict():
    """Item escrito que não vira veredito é recomendação, e a leitura é binária.

    A tabela do catálogo em `ANATOMY.md` nomeia cada item pelo id, em código
    inline na primeira coluna. Este teste é a amarra entre o documento e o
    executável: escrever um item lá sem implementá-lo aqui (ou o contrário) falha.
    """
    written = set(re.findall(r"^\| `([a-z0-9-]+)` \|", ANATOMY_DOC.read_text("utf-8"), re.M))

    assert written == {i.id for i in CATALOG}


# --- escopo por eixo: quem é avaliado, e quem não é ---------------------------


def test_an_infrastructure_repo_is_not_failed_by_a_node_item_it_has_no_surface_for():
    repo = conformant("panlabs-tech/tfbox", tipo="modulo-infraestrutura", surfaces=("python",))

    assert "node-lockfile-committed" not in rows(repo)


def test_a_repo_with_two_surfaces_is_evaluated_on_both():
    repo = without(conformant(surfaces=("python", "node")), ".python-version", ".node-version")

    assert {"python-runtime-declared", "node-runtime-declared"} <= set(rows(repo))


def test_a_repo_with_no_surface_at_all_is_not_failed_for_missing_surface_tooling():
    """Skills e dotfiles são o fixture mais importante do checker, não caso de borda."""
    assert rows(conformant("panlabs-tech/skills", tipo="skills")) == []


def test_an_org_invariant_is_charged_of_every_type_including_meta():
    """O repo que define o padrão não pode ser a primeira exceção a ele.

    Uma linha só, e não duas: o item por superfície só se aplica onde o portão
    existe. Sem o arquivo, o conserto é um, e a matriz pede um.
    """
    repo = conformant("panlabs-tech/.github", tipo="meta", surfaces=("python",))

    assert rows(without(repo, "lefthook.yml")) == ["portao-local-existe"]


def test_a_gate_that_exists_without_the_surface_tooling_is_its_own_row():
    repo = conformant("panlabs-tech/.github", tipo="meta", surfaces=("python",))
    repo["contents"] = {**repo["contents"], "lefthook.yml": "commit-msg:\n  commitlint\ngitleaks\n"}

    assert rows(repo) == ["python-portao-local-declara-ferramenta"]


# --- obrigatório versus condicional -------------------------------------------


def test_a_conditional_agent_doc_legitimately_absent_is_not_drift():
    """A ausência de um condicional fora do escopo dele é o resultado esperado.

    Os três condicionais (design, desenvolvimento local e MCPs) estão declarados
    no dado, e nenhum deles gera item: é assim que a distinção fica garantida em
    vez de depender de alguém lembrar dela.
    """
    conditional = load_anatomy().agent_docs_conditional or ()

    assert conditional
    assert rows(conformant()) == []


def test_a_required_agent_doc_absent_is_drift_with_the_reason_naming_which_one():
    repo = without(conformant(), "docs/agents/domain.md")

    assert rows(repo) == ["agent-docs-obrigatorios"]
    assert "docs/agents/domain.md" in row_for("agent-docs-obrigatorios", repo).reason


def test_local_services_absent_in_an_app_with_no_stateful_dependency_is_not_drift():
    """O falso positivo que a spec antecipou explicitamente, codificado."""
    sem_estado = conformant(tipo="aplicacao", surfaces=("node",), stateful=False)

    assert "aplicacao-composicao-de-servicos-locais" not in rows(sem_estado)


def test_local_services_absent_in_an_app_that_does_have_state_is_drift():
    com_estado = without(
        conformant(tipo="aplicacao", surfaces=("node",), stateful=True), "docker-compose.yml"
    )

    assert rows(com_estado) == ["aplicacao-composicao-de-servicos-locais"]


# --- slots: a declaração, nunca o valor ---------------------------------------


def test_a_slot_filled_with_different_values_passes_in_both_repos():
    um = conformant("panlabs-tech/um", surfaces=("python",))
    outro = {**conformant("panlabs-tech/outro", surfaces=("python",))}
    outro["contents"] = {**outro["contents"], ".python-version": "3.13\n"}

    assert rows(um, outro) == []


def test_a_slot_that_is_not_declared_at_all_fails():
    assert rows(without(conformant(surfaces=("python",)), ".python-version")) == [
        "python-runtime-declared"
    ]


def test_an_empty_slot_fails_even_though_the_file_exists():
    """Ausente, vazio e preenchido são três estados, e o slot só passa no terceiro."""
    repo = conformant()
    repo["contents"] = {**repo["contents"], "docs/agents/triage-labels.md": "\n"}

    assert rows(repo) == ["triage-labels-slot-declarado"]


def test_two_different_label_dialects_both_pass_and_no_dialect_is_hardcoded():
    """A fixture usa um dialeto inventado; se algum estivesse cravado, ela reprovaria."""
    canonico = conformant("panlabs-tech/canonico")
    canonico["contents"] = {
        **canonico["contents"],
        "docs/agents/triage-labels.md": "| papel | `ready-for-agent` |",
    }
    namespaced = conformant("panlabs-tech/namespaced")
    namespaced["contents"] = {
        **namespaced["contents"],
        "docs/agents/triage-labels.md": "| papel | `status:ready-for-agent` |",
    }

    assert rows(canonico, namespaced) == []


# --- o contrato de nomes de status --------------------------------------------


def test_zero_one_and_two_surfaces_produce_the_same_set_of_status_names():
    """É o que faz a lista fixa de required checks sobreviver a stack variável."""
    nenhuma = conformant("panlabs-tech/skills", tipo="skills")
    uma = conformant("panlabs-tech/uma", surfaces=("python",))
    duas = conformant("panlabs-tech/duas", surfaces=("python", "node"))

    assert rows(nenhuma, uma, duas) == []


def test_a_caller_that_does_not_publish_the_rollup_is_drift():
    repo = conformant()
    repo["contents"] = {
        **repo["contents"],
        ".github/workflows/pr-checks.yml": "jobs:\n  security:\n    uses: outro\n",
    }

    linha = row_for("contrato-de-nomes-de-status", repo)
    assert "checks" in linha.reason


# --- o que o repositório não versiona -----------------------------------------


def test_a_competing_agent_directory_is_drift_with_the_declared_reason():
    repo = conformant()
    repo["files"] = [*repo["files"], ".codex/config.toml.example"]

    linha = row_for("sem-configuracao-stale-de-ferramenta", repo)
    assert ".codex/" in linha.reason
    assert "agente concorrente" in linha.reason


def test_vendored_global_equipment_is_drift():
    repo = conformant()
    repo["files"] = [*repo["files"], ".claude/skills/tdd/SKILL.md", "skills-lock.json"]

    linha = row_for("sem-equipamento-global-versionado", repo)
    assert ".claude/skills/" in linha.reason
    assert "skills-lock.json" in linha.reason


def test_the_generic_agent_file_is_the_source_of_truth_and_the_primary_one_points_at_it():
    fossil = conformant()
    fossil["contents"] = {**fossil["contents"], "CLAUDE.md": "instruções próprias, sem referência"}

    assert rows(fossil) == ["agent-entrypoint-primario-referencia-generico"]


# --- o alvo é a org viva -------------------------------------------------------


def test_a_repo_new_to_the_live_org_enters_the_matrix_without_any_code_change():
    novo = without(conformant("panlabs-tech/recem-chegado"), "AGENTS.md")

    assert "agent-entrypoint-generico" in rows(novo)


def test_a_dot_prefixed_repo_name_enters_the_matrix_like_any_other():
    ponto = conformant("panlabs-tech/.github", tipo="meta", surfaces=("python",))
    ponto["has_license"] = False

    assert "license-exists" in rows(ponto)


def test_a_network_or_credential_failure_stays_distinguishable_from_anatomy_drift():
    quebrado = {"name": "panlabs-tech/instavel", "error": "HTTP 401: bad credentials"}
    derivado = without(conformant("panlabs-tech/nu"), "AGENTS.md")

    the_plan = planner.plan(observed(quebrado, derivado), CATALOG)
    verdicts = {row.target: row.payload["verdict"] for row in the_plan}

    assert verdicts["panlabs-tech/instavel"] == planner.ERROR_VERDICT
    assert verdicts["panlabs-tech/nu"] == planner.DRIFT_VERDICT


# --- o dado que o catálogo consome ---------------------------------------------


def test_the_dotfiles_repo_has_its_type_declared_in_the_data():
    assert load_repo_types()["panlabs-tech/dotfiles"] == "dotfiles"


def test_every_repo_of_the_live_org_is_classified():
    """Um tipo em branco deixa o eixo inteiro sem alcançar aquele repositório."""
    types = load_repo_types()

    assert set(types.values()) <= VALID_TYPES
    assert len(types) == 8


def test_an_undecided_dimension_produces_no_item_at_all():
    """`null` no dado é "ainda não decidido", e nada é cobrado para ele."""
    vazia = build(Anatomy(), Desired())

    assert [i.id for i in vazia] == ["readme-exists", "license-exists"]


def test_the_undecided_dimensions_are_reported_by_name():
    """Silêncio não pode ser lido como conformidade: o CLI diz o que falta decidir."""
    assert "surfaces.node.runtime_major" in load_anatomy().undecided


def test_a_path_rule_without_a_reason_is_refused():
    """Motivo é obrigatório num item de plano, e a regra que o gera não pode omiti-lo."""
    assert all(rule.why for rule in load_anatomy().stale_tool_paths or ())
    assert all(rule.why for rule in load_anatomy().global_equipment_paths or ())


def test_the_catalog_vocabulary_module_carries_no_item_of_its_own():
    assert not [name for name in vars(item) if name.isupper() and name.endswith("ITEMS")]
