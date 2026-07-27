"""O planner do checker: dado o estado observado, qual matriz de deriva sai dele.

O planner é puro. As fixtures são estado de repositório, não repositórios
reais -- os casos que importam (superfície ausente, tipo não declarado, slot
vazio) são estados que a frota real não necessariamente está hoje.

**O arranjo de cada teste é um repositório conforme com um defeito.** Com o
catálogo cheio, montar o estado item a item faria cada teste declarar trinta
fatos para falar de um, e ele passaria a falhar por motivo alheio ao que afirma.
`repo()` entrega a linha de base conforme; cada teste tira ou troca a única coisa
de que fala, e a asserção é sobre a lista **inteira** de ações, para que um item
novo não passe despercebido por baixo de um `in`.
"""

from typing import Any

from panlabs.checker import planner
from panlabs.checker.catalog.paths import PR_CHECKS
from panlabs.checker.desired import Desired
from panlabs.checker.model import Observed
from panlabs.checker.observe import build_observed
from panlabs.plan import Plan, PlanItem

# --- a linha de base conforme -------------------------------------------------

CANONICAL_DIALECT = """# Triage labels

| Papel na skill | Label neste tracker |
| `needs-triage` | `needs-triage` |
| `needs-info` | `needs-info` |
| `ready-for-agent` | `ready-for-agent` |
| `ready-for-human` | `ready-for-human` |
| `wontfix` | `wontfix` |
"""

NAMESPACED_DIALECT = """# Labels de triagem

Este repo usa o namespace `status:` para estados de workflow.

| Papel canônico | Label no repo |
| `needs-triage` | `status:needs-triage` |
| `needs-info` | `status:needs-info` |
| `ready-for-agent` | `status:ready-for-agent` |
| `ready-for-human` | `status:hitl` |
| `wontfix` | `status:wontfix` |
"""

LOCAL_GATE = """pre-commit:
  commands:
    gitleaks:
      run: gitleaks protect --staged
commit-msg:
  commands:
    commitlint:
      run: npx commitlint --edit
"""


def ci_yaml(*legs: str) -> str:
    """O caller de CI de um consumidor conforme, com as pernas que se pedir.

    Gerado em vez de escrito porque três itens diferentes leem este mesmo texto
    (a referência compartilhada, o contrato de nomes de status e a perna por
    superfície), e um YAML literal por teste faria cada um deles depender de a
    montagem do outro estar certa.
    """
    lines = ["name: pr-checks", "", "jobs:"]
    for leg in legs:
        lines += [f"  {leg}:", f"    uses: panlabs-tech/.github/.github/workflows/{leg}.yml@v1"]
    lines += [
        "  checks:",
        f"    needs: [{', '.join(legs)}]",
        "  security-scan:",
        "    uses: panlabs-tech/.github/.github/workflows/security.yml@v1",
        "  security:",
        "    needs: [security-scan]",
    ]
    return "\n".join(lines) + "\n"


BASE_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "docs/agents/issue-tracker.md",
    "docs/agents/triage-labels.md",
    "docs/agents/workflow.md",
    "docs/agents/domain.md",
    "lefthook.yml",
    PR_CHECKS,
)

BASE_CONTENTS: dict[str, str] = {
    "AGENTS.md": "# Orientação genérica, que é a fonte-da-verdade.\n",
    "CLAUDE.md": "@AGENTS.md\n\n## Específico do agente primário\n",
    "docs/agents/triage-labels.md": CANONICAL_DIALECT,
    "lefthook.yml": LOCAL_GATE,
    PR_CHECKS: ci_yaml(),
}


def repo(
    name: str = "panlabs-tech/conforme",
    *,
    tipo: str | None = None,
    files: list[str] | None = None,
    drop: list[str] | None = None,
    contents: dict[str, str] | None = None,
    has_readme: bool = True,
    has_license: bool = True,
    description: str | None = "um repositório da frota",
    topics: list[str] | None = None,
    has_wiki: bool = False,
    license: str | None = "MIT",
    error: str | None = None,
) -> dict[str, Any]:
    """Um repositório conforme, com o que o teste pedir tirado ou trocado.

    `drop` tira um caminho da linha de base **e** o conteúdo dele junto: um
    arquivo que sumiu da árvore e continuasse com conteúdo observado seria um
    estado que a plataforma não produz, e um teste montado sobre estado
    impossível não prova nada sobre a frota.
    """
    if error is not None:
        return {"name": name, "error": error}

    removed = set(drop or ())
    body = dict(BASE_CONTENTS)
    body.update(contents or {})

    tree = [path for path in [*BASE_FILES, *(files or ())] if path not in removed]
    body = {path: text for path, text in body.items() if path not in removed}

    return {
        "name": name,
        "tipo": tipo,
        "files": tree,
        "contents": body,
        "has_readme": has_readme,
        "has_license": has_license,
        "description": description,
        "topics": ["python"] if topics is None else topics,
        "has_wiki": has_wiki,
        "license": license,
    }


def python_repo(name: str = "panlabs-tech/py", **kwargs: Any) -> dict[str, Any]:
    """Um repositório conforme **com** superfície Python conforme."""
    files = ["pyproject.toml", ".python-version", *(kwargs.pop("files", None) or ())]
    contents = {
        ".python-version": "3.12\n",
        "pyproject.toml": "[tool.ruff]\nline-length = 100\n",
        PR_CHECKS: ci_yaml("checks-python"),
        **(kwargs.pop("contents", None) or {}),
    }
    return repo(name, files=files, contents=contents, **kwargs)


def node_repo(name: str = "panlabs-tech/node", **kwargs: Any) -> dict[str, Any]:
    """Um repositório conforme **com** superfície Node conforme."""
    files = ["package.json", ".node-version", "pnpm-lock.yaml", *(kwargs.pop("files", None) or ())]
    contents = {
        ".node-version": "24\n",
        "package.json": '{"devDependencies": {"biome": "^2"}}',
        PR_CHECKS: ci_yaml("checks-node"),
        **(kwargs.pop("contents", None) or {}),
    }
    return repo(name, files=files, contents=contents, **kwargs)


def observed(*repos: dict[str, Any]) -> Observed:
    return build_observed({"org": "panlabs-tech", "repos": list(repos)})


def items_for(the_plan: Plan, target: str) -> list[PlanItem]:
    return [item for item in the_plan if item.target == target]


def actions_for(the_plan: Plan, target: str) -> list[str]:
    return [item.action for item in items_for(the_plan, target)]


def row_for(the_plan: Plan, target: str, action: str) -> PlanItem:
    return next(row for row in items_for(the_plan, target) if row.action == action)


# --- a linha de base é mesmo conforme -----------------------------------------


def test_a_fully_conformant_repo_yields_no_rows_at_all():
    """Sem isto, todo teste abaixo poderia estar passando por acidente."""
    the_plan = planner.plan(observed(repo()))

    assert actions_for(the_plan, "panlabs-tech/conforme") == []


def test_a_conformant_repo_with_each_surface_yields_no_rows_either():
    the_plan = planner.plan(observed(python_repo(), node_repo()))

    assert actions_for(the_plan, "panlabs-tech/py") == []
    assert actions_for(the_plan, "panlabs-tech/node") == []


# --- escopo por eixo: stack não cobra o que não se aplica ---------------------


def test_a_terraform_only_repo_is_not_failed_by_any_node_scoped_item():
    state = observed(repo("panlabs-tech/tfbox", files=["main.tf"]))

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/tfbox") == []


def test_a_repo_with_no_surface_at_all_is_not_failed_for_a_missing_stack_leg():
    """`skills` e `dotfiles` são o fixture que importa, não o caso de borda."""
    state = observed(repo("panlabs-tech/skills", tipo="skills"))

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/skills") == []


def test_a_manifest_in_a_subfolder_puts_the_repo_in_scope_for_the_node_items():
    """O layout de workspace de pnpm que três repositórios da frota usam.

    Manifesto em `apps/web`, um lockfile na raiz servindo o workspace inteiro.
    Antes de a árvore ser recursiva, o item nem chegava a ser avaliado aqui.
    """
    state = observed(
        node_repo(
            "panlabs-tech/mono",
            files=["apps/web/package.json"],
            drop=["package.json"],
            contents={"apps/web/package.json": '{"devDependencies": {"biome": "^2"}}'},
        )
    )

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/mono") == []


def test_a_node_surface_with_no_lockfile_at_all_is_drift():
    state = observed(node_repo("panlabs-tech/mono", drop=["pnpm-lock.yaml"]))

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/mono") == ["node-lockfile-committed"]


def test_a_repo_with_two_surfaces_is_evaluated_on_both():
    state = observed(
        repo(
            "panlabs-tech/monorepo",
            files=["pyproject.toml", "package.json"],
            contents={PR_CHECKS: ci_yaml("checks-python", "checks-node")},
        )
    )

    actions = actions_for(planner.plan(state), "panlabs-tech/monorepo")

    assert "python-runtime-declared" in actions
    assert "node-runtime-declared" in actions
    assert "python-toolchain-declared" in actions
    assert "node-toolchain-declared" in actions


def test_the_ci_leg_a_surface_needs_is_charged_only_of_the_repo_that_has_it():
    """A perna que falta sai verde sem ter rodado nada: o rollup agrega o que existe."""
    sem_perna = observed(python_repo("panlabs-tech/py", contents={PR_CHECKS: ci_yaml()}))
    sem_superficie = observed(repo("panlabs-tech/skills", contents={PR_CHECKS: ci_yaml()}))

    assert actions_for(planner.plan(sem_perna), "panlabs-tech/py") == ["python-ci-leg"]
    assert actions_for(planner.plan(sem_superficie), "panlabs-tech/skills") == []


# --- invariante versus condicional --------------------------------------------


def test_a_missing_invariant_item_shows_up_as_drift_with_a_reason_naming_it():
    state = observed(repo("panlabs-tech/nu", has_readme=False))

    the_plan = planner.plan(state)

    item = items_for(the_plan, "panlabs-tech/nu")[0]
    assert item.action == "readme-exists"
    assert "README" in item.reason
    assert item.payload["scope"] == "invariante de org"
    assert item.payload["verdict"] == planner.DRIFT_VERDICT


def test_an_invariant_item_is_charged_of_the_meta_repo_like_of_any_other():
    """O repo que carrega a definição do padrão não é a primeira exceção a ele."""
    state = observed(repo("panlabs-tech/.github", tipo="meta", files=["ANATOMY.md"], topics=[]))

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/.github") == ["repo-topics-declared"]


def test_a_missing_mandatory_agent_doc_names_which_one_is_missing():
    state = observed(repo("panlabs-tech/nu", drop=["docs/agents/domain.md"]))

    item = items_for(planner.plan(state), "panlabs-tech/nu")[0]

    assert item.action == "agent-doc-domain"
    assert "docs/agents/domain.md" in item.reason


def test_the_four_mandatory_agent_docs_are_each_their_own_row():
    state = observed(
        repo(
            "panlabs-tech/nu",
            drop=[
                "docs/agents/issue-tracker.md",
                "docs/agents/triage-labels.md",
                "docs/agents/workflow.md",
                "docs/agents/domain.md",
            ],
        )
    )

    assert actions_for(planner.plan(state), "panlabs-tech/nu") == [
        "agent-doc-issue-tracker",
        "agent-doc-triage-labels",
        "agent-doc-workflow",
        "agent-doc-domain",
    ]


def test_a_conditional_agent_doc_legitimately_out_of_scope_does_not_appear_at_all():
    """A ausência de um condicional fora da condição é o resultado esperado."""
    state = observed(repo("panlabs-tech/sem-mcp"))

    actions = actions_for(planner.plan(state), "panlabs-tech/sem-mcp")

    assert "agent-doc-mcps" not in actions
    assert "agent-doc-local-dev" not in actions
    assert "agent-doc-design" not in actions


def test_a_conditional_agent_doc_inside_its_condition_is_charged_like_any_other():
    """Condicional não é opcional: dentro da condição, ele é obrigatório."""
    state = observed(repo("panlabs-tech/com-mcp", files=[".mcp.json"]))

    assert actions_for(planner.plan(state), "panlabs-tech/com-mcp") == ["agent-doc-mcps"]


def test_the_local_dev_doc_is_charged_only_of_a_repo_that_composes_local_services():
    com = observed(repo("panlabs-tech/com", files=["docker-compose.yml"]))
    sem = observed(repo("panlabs-tech/sem"))

    assert actions_for(planner.plan(com), "panlabs-tech/com") == ["agent-doc-local-dev"]
    assert actions_for(planner.plan(sem), "panlabs-tech/sem") == []


def test_a_missing_document_is_one_row_and_not_two():
    """A ausência do documento é a linha de um item; o conteúdo dele é de outro.

    Sem o `applies` do item de conteúdo, um arquivo que falta produziria duas
    linhas dizendo a mesma coisa, e a matriz contaria deriva em dobro.
    """
    state = observed(repo("panlabs-tech/nu", drop=["docs/agents/triage-labels.md"]))

    assert actions_for(planner.plan(state), "panlabs-tech/nu") == ["agent-doc-triage-labels"]


# --- o fóssil da orientação de agente -----------------------------------------


def test_a_primary_guidance_file_that_duplicates_the_generic_one_is_drift():
    """O fóssil medido na frota: os dois arquivos com o mesmo conteúdo.

    Um deles deixa de ser atualizado e passa a descrever um estado que já não é
    verdade -- sem que nada acuse, porque os dois existem.
    """
    duplicado = "# a mesma orientação, duas vezes\n"
    state = observed(
        repo("panlabs-tech/fossil", contents={"AGENTS.md": duplicado, "CLAUDE.md": duplicado})
    )

    item = items_for(planner.plan(state), "panlabs-tech/fossil")[0]

    assert item.action == "agent-guidance-primary-defers-to-generic"
    assert "idêntico" in item.reason


def test_a_primary_guidance_file_that_ignores_the_generic_one_is_drift():
    state = observed(repo("panlabs-tech/solto", contents={"CLAUDE.md": "# só as minhas regras\n"}))

    item = items_for(planner.plan(state), "panlabs-tech/solto")[0]

    assert item.action == "agent-guidance-primary-defers-to-generic"
    assert "não referencia" in item.reason


def test_a_repo_without_the_generic_guidance_file_is_charged_once_not_twice():
    state = observed(repo("panlabs-tech/nu", drop=["AGENTS.md"]))

    assert actions_for(planner.plan(state), "panlabs-tech/nu") == ["agent-guidance-generic-exists"]


# --- slots: a anatomia cobra a declaração, nunca o valor ----------------------


def test_a_slot_filled_with_different_values_passes_in_both_repos():
    """O teste que prova que o checker cobra declaração, e não valor."""
    state = observed(
        python_repo("panlabs-tech/a", contents={".python-version": "3.12\n"}),
        python_repo("panlabs-tech/b", contents={".python-version": "3.13\n"}),
    )

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/a") == []
    assert actions_for(the_plan, "panlabs-tech/b") == []


def test_an_empty_slot_fails_just_like_an_undeclared_one():
    """Ausente e vazio são estados diferentes da observação e o mesmo veredito aqui.

    Um arquivo de versão vazio declara tanto quanto um que não existe, e a
    anatomia obriga a declaração, não o arquivo.
    """
    vazio = observed(python_repo("panlabs-tech/vazio", contents={".python-version": "   \n"}))
    ausente = observed(python_repo("panlabs-tech/ausente", drop=[".python-version"]))

    assert actions_for(planner.plan(vazio), "panlabs-tech/vazio") == ["python-runtime-declared"]
    assert actions_for(planner.plan(ausente), "panlabs-tech/ausente") == ["python-runtime-declared"]


def test_a_runtime_slot_buried_in_a_subfolder_does_not_satisfy_the_root_declaration():
    """A árvore inteira é observada, e é justamente por isso que o caminho importa.

    O gerenciador de runtime da máquina lê a declaração na raiz do repo; uma
    homônima enterrada numa subpasta não é a mesma declaração.
    """
    state = observed(
        python_repo("panlabs-tech/app", files=["docs/.python-version"], drop=[".python-version"])
    )

    assert actions_for(planner.plan(state), "panlabs-tech/app") == ["python-runtime-declared"]


def test_two_declared_label_dialects_both_pass():
    """O teste que impede o checker de cravar um dialeto de label.

    Os dois são reais: um repositório da frota usa o vocabulário canônico
    verbatim, outro usa prefixo de namespace com uma família ortogonal a mais.
    """
    state = observed(
        repo("panlabs-tech/canonico", contents={"docs/agents/triage-labels.md": CANONICAL_DIALECT}),
        repo(
            "panlabs-tech/namespace", contents={"docs/agents/triage-labels.md": NAMESPACED_DIALECT}
        ),
    )

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/canonico") == []
    assert actions_for(the_plan, "panlabs-tech/namespace") == []


def test_a_label_document_that_declares_no_vocabulary_at_all_fails():
    state = observed(
        repo(
            "panlabs-tech/mudo",
            contents={"docs/agents/triage-labels.md": "# Labels\n\nA definir.\n"},
        )
    )

    item = items_for(planner.plan(state), "panlabs-tech/mudo")[0]

    assert item.action == "triage-vocabulary-declared"
    assert "ready-for-human" in item.reason


# --- o contrato de nomes de status --------------------------------------------


def test_zero_one_and_two_surfaces_are_charged_the_same_status_contract():
    """A lista fixa de required checks da org precisa sobreviver a stack variável.

    O item é invariante, e é por isso que um repositório sem superfície nenhuma
    também o carrega: sem o rollup, o merge dele fica pendurado para sempre
    esperando um check que ninguém publica.
    """
    sem_contrato = ci_yaml().replace("\n  checks:", "\n  outro-nome:")
    state = observed(
        repo("panlabs-tech/zero", contents={PR_CHECKS: sem_contrato}),
        python_repo("panlabs-tech/uma", contents={PR_CHECKS: sem_contrato}),
        repo(
            "panlabs-tech/duas",
            files=[
                "pyproject.toml",
                "package.json",
                ".python-version",
                ".node-version",
                "pnpm-lock.yaml",
            ],
            contents={
                PR_CHECKS: sem_contrato,
                ".python-version": "3.12\n",
                ".node-version": "24\n",
                "pyproject.toml": "[tool.ruff]\n",
                "package.json": '{"devDependencies": {"biome": "^2"}}',
            },
        ),
    )

    the_plan = planner.plan(state)

    for target in ("panlabs-tech/zero", "panlabs-tech/uma", "panlabs-tech/duas"):
        assert "status-rollup-contract" in actions_for(the_plan, target)


def test_a_ci_that_copies_yaml_instead_of_referencing_the_shared_workflows_is_drift():
    copiado = ci_yaml().replace("panlabs-tech/.github/.github/workflows/", "./.github/workflows/")
    state = observed(repo("panlabs-tech/copiador", contents={PR_CHECKS: copiado}))

    assert actions_for(planner.plan(state), "panlabs-tech/copiador") == [
        "ci-references-shared-workflows"
    ]


def test_the_repo_that_publishes_the_shared_workflows_may_reference_them_locally():
    """Um caller no mesmo repo resolve contra o próprio SHA, e é o único que pode.

    Sem esta exceção, o repo meta reprovaria por usar a única forma que funciona
    nele; com ela valendo para todos, o item se esvaziaria, porque referenciar
    workflow local é exatamente o que copiar YAML produz.
    """
    local = ci_yaml().replace("panlabs-tech/.github/.github/workflows/", "./.github/workflows/")
    state = observed(
        repo("panlabs-tech/.github", tipo="meta", files=["ANATOMY.md"], contents={PR_CHECKS: local})
    )

    assert actions_for(planner.plan(state), "panlabs-tech/.github") == []


# --- os dois portões e a disciplina de versionamento --------------------------


def test_a_repo_without_a_local_gate_is_charged_once_and_not_for_the_scan_too():
    state = observed(repo("panlabs-tech/sem-portao", drop=["lefthook.yml"]))

    assert actions_for(planner.plan(state), "panlabs-tech/sem-portao") == [
        "local-commit-gate-exists",
        "commit-message-standard-declared",
    ]


def test_a_local_gate_that_does_not_scan_for_secrets_is_drift():
    state = observed(
        repo(
            "panlabs-tech/sem-scan",
            contents={"lefthook.yml": "commit-msg:\n  commands:\n    commitlint:\n      run: x\n"},
        )
    )

    assert actions_for(planner.plan(state), "panlabs-tech/sem-scan") == [
        "secret-scan-before-commit"
    ]


def test_the_commit_message_standard_may_be_declared_by_a_linter_config_instead():
    """O item cobra o fato, e a frota o realiza por dois caminhos diferentes."""
    state = observed(
        repo(
            "panlabs-tech/por-arquivo",
            files=["commitlint.config.mjs"],
            contents={"lefthook.yml": "pre-commit:\n  commands:\n    gitleaks:\n      run: x\n"},
        )
    )

    assert actions_for(planner.plan(state), "panlabs-tech/por-arquivo") == []


# --- fóssil de ferramenta e equipamento global --------------------------------


def test_stale_tool_config_is_drift_and_the_reason_names_what_was_found():
    state = observed(
        repo("panlabs-tech/fossil", files=[".codex/config.toml", ".serena/project.yml"])
    )

    item = items_for(planner.plan(state), "panlabs-tech/fossil")[0]

    assert item.action == "no-stale-tool-config"
    assert ".codex" in item.reason
    assert ".serena" in item.reason


def test_versioned_global_equipment_is_drift():
    state = observed(
        repo(
            "panlabs-tech/vendorizado",
            files=[".claude/skills/tdd/SKILL.md", ".claude/settings.json"],
        )
    )

    item = items_for(planner.plan(state), "panlabs-tech/vendorizado")[0]

    assert item.action == "no-vendored-agent-equipment"
    assert ".claude/settings.json" in item.reason


def test_a_marker_file_declaring_adherence_to_a_global_mechanism_is_not_drift():
    """Marcador é declaração, e a lógica que ele aciona continua fora do repo."""
    state = observed(repo("panlabs-tech/aderente", files=[".claude/portable-hooks"]))

    assert actions_for(planner.plan(state), "panlabs-tech/aderente") == []


# --- itens de tipo ------------------------------------------------------------


def test_the_type_scoped_item_is_charged_only_against_its_declared_type():
    missing = observed(repo("panlabs-tech/.github", tipo="meta"))
    present = observed(repo("panlabs-tech/.github", tipo="meta", files=["ANATOMY.md"]))

    assert actions_for(planner.plan(missing), "panlabs-tech/.github") == ["anatomy-doc-exists"]
    assert actions_for(planner.plan(present), "panlabs-tech/.github") == []


def test_an_unclassified_repo_is_reached_by_no_type_item_and_that_is_not_drift():
    state = observed(repo("panlabs-tech/sem-tipo", tipo=None))

    actions = actions_for(planner.plan(state), "panlabs-tech/sem-tipo")

    assert not [action for action in actions if action.startswith("app-")]
    assert "anatomy-doc-exists" not in actions


def test_the_infrastructure_module_is_not_reached_by_the_application_package_rule():
    """Variante declarada, não exceção: ele fica de fora **por escopo**.

    O módulo de infraestrutura usa o gerenciador divergente e continua conforme:
    a regra de convergência é do tipo aplicação e não o alcança. Ficar de fora por
    escopo é revisável na matriz; ficar de fora por um `if` some no código.
    """
    state = observed(
        node_repo(
            "panlabs-tech/tfbox",
            tipo="modulo-infraestrutura",
            files=["package-lock.json", "main.tf"],
            drop=["pnpm-lock.yaml"],
        )
    )

    assert actions_for(planner.plan(state), "panlabs-tech/tfbox") == []


def test_an_application_on_the_divergent_package_manager_is_drift():
    state = observed(
        node_repo(
            "panlabs-tech/vitrine",
            tipo="aplicacao",
            files=["package-lock.json", ".mcp.json", ".env.example", "apps/web/page.tsx"],
            drop=["pnpm-lock.yaml"],
        )
    )

    item = row_for(planner.plan(state), "panlabs-tech/vitrine", "app-package-manager-single")

    assert "package-lock.json" in item.reason
    assert item.payload["scope"] == "tipo aplicacao"


def test_an_application_missing_a_container_build_next_to_one_of_its_apps():
    state = observed(
        node_repo(
            "panlabs-tech/app",
            tipo="aplicacao",
            files=[
                "apps/web/page.tsx",
                "apps/web/Dockerfile",
                "apps/api/main.py",
                ".mcp.json",
                ".env.example",
            ],
        )
    )

    item = row_for(planner.plan(state), "panlabs-tech/app", "app-container-build")

    assert "apps/api" in item.reason
    assert "apps/web" not in item.reason


def test_a_local_services_composition_missing_from_a_stateless_application_is_not_drift():
    """O falso positivo que a spec antecipou por escrito, codificado.

    A vitrine da frota legitimamente não tem dependência local com estado, e a
    ausência de composição lá é o resultado esperado, não deriva.
    """
    state = observed(
        node_repo(
            "panlabs-tech/vitrine",
            tipo="aplicacao",
            files=["apps/web/page.tsx", "apps/web/Dockerfile", ".mcp.json", ".env.example"],
        )
    )

    assert "app-local-services-composition" not in actions_for(
        planner.plan(state), "panlabs-tech/vitrine"
    )


def test_a_local_services_composition_missing_from_a_stateful_application_is_drift():
    state = observed(
        node_repo(
            "panlabs-tech/app",
            tipo="aplicacao",
            files=[
                "apps/web/page.tsx",
                "apps/web/Dockerfile",
                "apps/api/Dockerfile",
                "apps/api/alembic/versions/0001.py",
                ".mcp.json",
                ".env.example",
                "docs/agents/mcps.md",
            ],
        )
    )

    assert actions_for(planner.plan(state), "panlabs-tech/app") == [
        "app-local-services-composition"
    ]


def test_an_application_that_ships_only_the_mcp_example_still_owes_the_real_file():
    """O padrão atual da frota: exemplo versionado, configuração real gitignorada.

    O exemplo aciona o documento condicional de MCPs **e** continua devendo a
    configuração de verdade. São perguntas diferentes, e por isso itens diferentes.
    """
    state = observed(
        node_repo(
            "panlabs-tech/app",
            tipo="aplicacao",
            files=[
                "apps/web/page.tsx",
                "apps/web/Dockerfile",
                ".mcp.json.example",
                ".env.example",
                "docs/agents/mcps.md",
            ],
        )
    )

    assert actions_for(planner.plan(state), "panlabs-tech/app") == ["app-mcp-config-versioned"]


# --- valor decidido versus valor ainda não decidido ---------------------------


def test_an_undecided_dimension_is_not_evaluated_and_that_is_not_conformity():
    """`null` no dado não é conformidade: é ausência de pergunta."""
    state = observed(repo("panlabs-tech/qualquer", license="Apache-2.0"))

    assert actions_for(planner.plan(state, Desired()), "panlabs-tech/qualquer") == []


def test_a_decided_license_turns_the_uniformity_item_on_for_the_whole_fleet():
    state = observed(
        repo("panlabs-tech/mit", license="MIT"),
        repo("panlabs-tech/apache", license="Apache-2.0"),
    )

    the_plan = planner.plan(state, Desired(license="MIT"))

    assert actions_for(the_plan, "panlabs-tech/mit") == []
    assert actions_for(the_plan, "panlabs-tech/apache") == ["license-uniform"]


def test_a_repo_with_no_license_at_all_is_charged_once_and_not_for_uniformity_too():
    state = observed(repo("panlabs-tech/nu", has_license=False, license=None))

    the_plan = planner.plan(state, Desired(license="MIT"))

    assert actions_for(the_plan, "panlabs-tech/nu") == ["license-exists"]


def test_a_decided_runtime_series_charges_the_repo_that_declared_another_one():
    """Declarar é o slot; declarar a **mesma** coisa é o item de convergência.

    Um repositório pode declarar e mesmo assim divergir, e é por isso que são
    dois itens e não um.
    """
    state = observed(
        node_repo("panlabs-tech/novo", contents={".node-version": "24\n"}),
        node_repo("panlabs-tech/velho", contents={".node-version": "v22.14.0\n"}),
    )

    the_plan = planner.plan(state, Desired(node_series="24"))

    assert actions_for(the_plan, "panlabs-tech/novo") == []
    assert actions_for(the_plan, "panlabs-tech/velho") == ["node-runtime-converged"]


def test_the_series_of_python_is_not_the_major_and_a_patch_inside_it_still_passes():
    """Em Python a unidade em que "verde significa o mesmo" é `3.12`, não `3`.

    `3.12` e `3.13` divergem em comportamento de biblioteca, então compará-las
    pelo major aprovaria uma frota que de fato não converge. A regra é a série
    como prefixo, e ela serve às duas superfícies: `3.12` aceita `3.12.4` e
    recusa `3.13`, e em Node a série continua sendo o major.
    """
    state = observed(
        python_repo("panlabs-tech/certo", contents={".python-version": "3.12.4\n"}),
        python_repo("panlabs-tech/errado", contents={".python-version": "3.13\n"}),
    )

    the_plan = planner.plan(state, Desired(python_series="3.12"))

    assert actions_for(the_plan, "panlabs-tech/certo") == []
    assert actions_for(the_plan, "panlabs-tech/errado") == ["python-runtime-converged"]


def test_an_undeclared_runtime_slot_is_charged_once_and_not_for_convergence_too():
    """Um slot vazio já tem a sua linha; cobrar convergência dele seria dizer duas vezes."""
    state = observed(python_repo("panlabs-tech/nu", drop=[".python-version"]))

    the_plan = planner.plan(state, Desired(python_series="3.12"))

    assert actions_for(the_plan, "panlabs-tech/nu") == ["python-runtime-declared"]


def test_the_wiki_exception_comes_from_the_org_data_and_is_never_hardcoded():
    """O repo em que o wiki é gerado por automação de release não é deriva.

    A lista de exceções é dado de `config/org.json`, lida pelo mesmo loader que o
    script de org usa. Duplicá-la aqui criaria duas listas que divergem no dia em
    que uma for editada.
    """
    desired = Desired(wiki=False, wiki_exceptions=frozenset({"panlabs-tech/tfbox"}))
    state = observed(
        repo("panlabs-tech/tfbox", has_wiki=True),
        repo("panlabs-tech/outro", has_wiki=True),
    )

    the_plan = planner.plan(state, desired)

    assert actions_for(the_plan, "panlabs-tech/tfbox") == []
    assert actions_for(the_plan, "panlabs-tech/outro") == ["wiki-off-unless-declared"]


# --- canal de erro, distinto de deriva ----------------------------------------


def test_an_observation_failure_yields_an_error_verdict_not_a_drift_verdict():
    state = observed(repo("panlabs-tech/instavel", error="HTTP 401: bad credentials"))

    the_plan = planner.plan(state)

    items = items_for(the_plan, "panlabs-tech/instavel")
    assert len(items) == 1
    assert items[0].payload["verdict"] == planner.ERROR_VERDICT
    assert items[0].payload["verdict"] != planner.DRIFT_VERDICT
    assert "bad credentials" in items[0].reason


def test_one_repos_observation_failure_does_not_swallow_the_others_drift():
    state = observed(
        repo("panlabs-tech/instavel", error="timeout"),
        repo("panlabs-tech/nu", has_license=False),
    )

    the_plan = planner.plan(state)

    assert actions_for(the_plan, "panlabs-tech/instavel") == ["erro-observacao"]
    assert actions_for(the_plan, "panlabs-tech/nu") == ["license-exists"]


# --- alvo derivado e ordem estável ---------------------------------------------


def test_a_repo_new_to_the_live_org_enters_the_matrix_without_any_code_change():
    state = observed(repo("panlabs-tech/recem-chegado", has_readme=False))

    assert actions_for(planner.plan(state), "panlabs-tech/recem-chegado") == ["readme-exists"]


def test_a_dot_prefixed_repo_name_enters_the_matrix_like_any_other():
    state = observed(
        repo("panlabs-tech/.github", tipo="meta", files=["ANATOMY.md"], has_license=False)
    )

    assert actions_for(planner.plan(state), "panlabs-tech/.github") == ["license-exists"]


def test_the_plan_is_ordered_by_repo_name_whatever_order_the_org_listed_them_in():
    state = observed(
        repo("panlabs-tech/zulu", has_readme=False),
        repo("panlabs-tech/alfa", has_readme=False),
        repo("panlabs-tech/mike", has_readme=False),
    )

    targets = [item.target for item in planner.plan(state)]

    assert targets == ["panlabs-tech/alfa", "panlabs-tech/mike", "panlabs-tech/zulu"]
