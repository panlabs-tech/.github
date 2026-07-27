"""Os itens invariantes: cobrados de todo repositório, de todo tipo e stack.

Um item só mora aqui se a ausência dele é deriva em **qualquer** repositório da
org, sem condição nenhuma. Na dúvida, o item é de stack ou de tipo: um invariante
falso cobra de quem não deve, e é o falso positivo mais caro que existe aqui,
porque ele desgasta a matriz inteira.

Três itens deste módulo aparecem na spec de Repo #4 sob a narrativa de stack, e
mesmo assim moram aqui: a existência do portão local, a referência à CI
compartilhada e o contrato de nomes de status. O eixo de um item é o **escopo em
que ele é avaliado**, não o assunto de que ele fala, e os três são avaliados em
todo repositório -- inclusive num sem superfície nenhuma, que é justamente o caso
em que o rollup precisa existir para o merge não ficar pendurado para sempre. O
que varia por superfície é o que cada portão **roda**, e isso mora em `stack.py`.
"""

from __future__ import annotations

from panlabs.checker.catalog.item import (
    ORG,
    AnatomyItem,
    Predicate,
    all_of,
    always,
    any_of,
    declares,
    has_any_file,
    has_file,
    job_declared,
    paths_under,
)
from panlabs.checker.catalog.paths import (
    COMPOSE_FILES,
    MCP_CONFIG,
    MCP_EXAMPLE,
    NODE_MANIFESTS,
    PR_CHECKS,
)
from panlabs.checker.desired import Desired
from panlabs.checker.model import RepoObserved
from panlabs.ci.rollup import ROLLUP_CHECK_NAME, SECURITY_CHECK_NAME

__all__ = ["ITEMS"]

GENERIC_GUIDANCE = "AGENTS.md"
PRIMARY_GUIDANCE = "CLAUDE.md"
"""O genérico é a fonte-da-verdade; o do agente primário só o referencia.

Os dois nomes são valor decidido, não slot: o genérico é convenção de ecossistema
(o arquivo que qualquer ferramenta de agente lê) e o primário é o do agente que
esta org de fato usa. Um repo que troque de agente primário troca este item, e é
por isso que os dois nomes moram escritos num lugar só.
"""

AGENT_DOCS_DIR = "docs/agents/"
TRIAGE_DOC = f"{AGENT_DOCS_DIR}triage-labels.md"

TRIAGE_ROLES = ("needs-triage", "needs-info", "ready-for-agent", "ready-for-human", "wontfix")
"""Os cinco **papéis** de triagem das skills, que não são os labels de repo nenhum.

Esta é a linha de que o vocabulário-como-slot depende de ninguém confundir. O item
cobra que o documento declare o mapa dos cinco papéis; qual string cada papel vira
naquele repo é dele. A frota usa pelo menos dois dialetos -- um com o canônico
verbatim e outro com prefixo de namespace mais uma família ortogonal -- e os dois
passam. Cravar o label aqui reprovaria um repo conforme por ele ter escolhido
diferente, que é o oposto do que um slot significa.
"""

UI_FRAMEWORKS = ('"next"', '"react"')
"""O que aciona o documento condicional de design: o repositório tem interface.

A condição é fato do repositório, não eixo: ela não pergunta o tipo nem avalia por
superfície, pergunta se existe interface para haver design. Um repositório sem
interface nenhuma não é cobrado do documento, e essa ausência não é deriva.
"""

SHARED_CI_REF = "panlabs-tech/.github/.github/workflows/"
"""A forma versionada com que um consumidor referencia a CI compartilhada."""

LOCAL_CI_REF = "uses: ./.github/workflows/"
"""A forma local, válida **só** no repo que publica os workflows compartilhados.

Um caller no mesmo repo sempre resolve contra o próprio SHA, o que evita o
ovo-e-a-galinha de uma tag que ainda não existe no commit que a introduz. Aceitar
esta forma em qualquer repo esvaziaria o item: "referencia workflow local" é
exatamente o que copiar YAML produz.
"""

LOCAL_GATES = ("lefthook.yml", ".pre-commit-config.yaml")
"""As formas de portão local que a frota usa. O item cobra que exista **um**."""

COMMIT_LINTERS = (
    "commitlint.config.mjs",
    "commitlint.config.js",
    "commitlint.config.ts",
    "commitlint.config.cjs",
    ".commitlintrc.json",
)

SECRET_SCANNER = "gitleaks"
"""Valor decidido, não slot, e a razão é a mesma que faz os dois portões existirem.

O portão de CI compartilhado roda `gitleaks` (`.github/workflows/security.yml`).
Um portão local que rodasse outro scanner faria "passou no local" e "passou na CI"
significarem coisas diferentes, que é precisamente o que o par de portões existe
para impedir.
"""

STALE_TOOL_CONFIG = (".codex/", ".serena/", ".cursor/", ".windsurf/", ".continue/", ".aider")
"""Configuração de ferramenta fora da toolchain decidida na spec de Máquina.

Duas destas são resíduo medido, não hipótese: diretório de agente concorrente em
quatro repositórios e de ferramenta de indexação num quinto. As demais entram por
serem da mesma espécie. **O checker só alarma**: remover é trabalho de retrofit, e
a remoção tem um preflight obrigatório que nenhum script executa -- aquilo é
candidato a promoção global? Hoje é operação nula, porque o resíduo mais comum é
configuração de MCP, que o mecanismo versionado já cobre, mas a ordem importa para
não apagar capacidade por engano.
"""

VENDORED_EQUIPMENT = (
    ".claude/skills/",
    ".claude/agents/",
    ".claude/commands/",
    ".claude/hooks/",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".agents/skills/",
    ".agents/agents/",
    ".agents/commands/",
    ".agents/hooks/",
)
"""Equipamento global que um repositório não versiona -- por design, não por omissão.

Skill, subagente, comando, a lógica dos hooks portáveis, a lista de permissões e a
barra de status vivem num lugar só: o global. A cláusula operante é zero
redundância, e é ela que dissolve a inversão de precedência entre níveis, porque
elimina colisão de nome.

O que **é** versionado é o arquivo marcador que declara adesão a um mecanismo
global. Ele não cai nesta lista de propósito: marcador é declaração, e a lógica que
ele aciona continua fora.
"""


def _defers_to_generic(repo: RepoObserved, desired: Desired) -> bool:
    """O arquivo do agente primário referencia o genérico em vez de duplicá-lo."""
    del desired
    primary = repo.content(PRIMARY_GUIDANCE)
    if primary is None:
        return False
    if primary == repo.content(GENERIC_GUIDANCE):
        return False
    return GENERIC_GUIDANCE in primary


def _why_not_deferred(repo: RepoObserved, desired: Desired) -> str:
    """As três formas de falhar o item, nomeadas: some, duplica ou ignora."""
    del desired
    primary = repo.content(PRIMARY_GUIDANCE)
    if primary is None:
        return f"{repo.name} tem {GENERIC_GUIDANCE} mas não tem {PRIMARY_GUIDANCE}"
    if primary == repo.content(GENERIC_GUIDANCE):
        return (
            f"{repo.name} tem {PRIMARY_GUIDANCE} e {GENERIC_GUIDANCE} com conteúdo idêntico: "
            "são duas cópias da mesma orientação, e a segunda é a que vira fóssil"
        )
    return (
        f"{repo.name} tem {PRIMARY_GUIDANCE} que não referencia {GENERIC_GUIDANCE}, "
        "então a fonte-da-verdade não é a genérica"
    )


def _agent_doc(
    name: str,
    assunto: str,
    quando: Predicate = always,
    porque: str = "",
    reads: tuple[str, ...] = (),
) -> AnatomyItem:
    """Um documento de configuração de agente, de nome fixo.

    Um item por documento, e não um item para o conjunto: a matriz precisa nomear
    **qual** falta, e um item agregado diria só que algum falta.

    `quando` é o que separa os quatro obrigatórios dos três condicionais. Um
    condicional fora da sua condição não gera linha nenhuma: a ausência dele ali é
    o resultado esperado, e confundi-la com deriva é o falso positivo que a
    anatomia existe para prevenir. Onde a condição vale, ele é cobrado igual a
    qualquer obrigatório -- condicional não é opcional.
    """
    path = f"{AGENT_DOCS_DIR}{name}.md"
    return AnatomyItem(
        id=f"agent-doc-{name}",
        scope=ORG,
        applies=quando,
        satisfied=has_file(path),
        motivo=lambda repo, desired: (
            f"{repo.name} não tem {path}, o documento de {assunto}"
            + (f", exigido porque {porque}" if porque else ", que todo repo declara")
        ),
        reads=reads,
    )


ITEMS: tuple[AnatomyItem, ...] = (
    AnatomyItem(
        id="readme-exists",
        scope=ORG,
        applies=always,
        satisfied=lambda repo, desired: repo.has_readme,
        motivo=lambda repo, desired: f"{repo.name} não tem README",
    ),
    AnatomyItem(
        id="license-exists",
        scope=ORG,
        applies=always,
        satisfied=lambda repo, desired: repo.has_license,
        motivo=lambda repo, desired: f"{repo.name} não tem LICENSE",
    ),
    AnatomyItem(
        id="license-uniform",
        scope=ORG,
        # Só onde há licença: um repo sem licença nenhuma já é a linha do item
        # acima, e cobrar uniformidade dele diria a mesma coisa duas vezes.
        applies=lambda repo, desired: desired.license is not None and repo.has_license,
        satisfied=lambda repo, desired: repo.license == desired.license,
        motivo=lambda repo, desired: (
            f"{repo.name} tem licença {repo.license}, e a org converge para {desired.license}"
        ),
    ),
    AnatomyItem(
        id="repo-description-declared",
        scope=ORG,
        applies=always,
        satisfied=lambda repo, desired: bool((repo.description or "").strip()),
        motivo=lambda repo, desired: (
            f"{repo.name} não tem descrição, e a listagem da org fica ilegível sem abrir o repo"
        ),
    ),
    AnatomyItem(
        id="repo-topics-declared",
        scope=ORG,
        applies=always,
        satisfied=lambda repo, desired: bool(repo.topics),
        motivo=lambda repo, desired: (
            f"{repo.name} não declara topic nenhum, e é por topic que a frota se filtra por stack"
        ),
    ),
    AnatomyItem(
        id="wiki-off-unless-declared",
        scope=ORG,
        # A exceção é dado de `config/org.json`, lida e não cravada: o repo em que
        # o wiki é gerado por automação de release está lá, e desligá-lo quebraria
        # a automação. Um `if` no lugar desta linha seria a exceção escondida.
        applies=lambda repo, desired: (
            desired.wiki is not None and repo.name not in desired.wiki_exceptions
        ),
        satisfied=lambda repo, desired: repo.has_wiki == desired.wiki,
        motivo=lambda repo, desired: (
            f"{repo.name} tem wiki ligado sem estar na lista de exceções de config/org.json: "
            "é superfície vazia que ninguém mantém"
        ),
    ),
    AnatomyItem(
        id="agent-guidance-generic-exists",
        scope=ORG,
        applies=always,
        satisfied=has_file(GENERIC_GUIDANCE),
        motivo=lambda repo, desired: (
            f"{repo.name} não tem {GENERIC_GUIDANCE}, que é a fonte-da-verdade da orientação "
            "de agente"
        ),
    ),
    AnatomyItem(
        id="agent-guidance-primary-defers-to-generic",
        scope=ORG,
        # Só onde o genérico existe: sem ele, a linha a ler é a do item acima.
        applies=has_file(GENERIC_GUIDANCE),
        satisfied=_defers_to_generic,
        motivo=_why_not_deferred,
        reads=(PRIMARY_GUIDANCE, GENERIC_GUIDANCE),
    ),
    # Os quatro de nome fixo, cobrados de todo repositório.
    _agent_doc("issue-tracker", "tracker de issues"),
    _agent_doc("triage-labels", "vocabulário de labels de triagem"),
    _agent_doc("workflow", "fluxo de trabalho"),
    _agent_doc("domain", "domínio"),
    # Os três condicionais, cobrados só onde a condição que os aciona vale.
    _agent_doc(
        "design",
        "design",
        quando=declares(NODE_MANIFESTS, UI_FRAMEWORKS),
        porque="ele tem interface declarada em manifesto Node",
        reads=NODE_MANIFESTS,
    ),
    _agent_doc(
        "local-dev",
        "desenvolvimento local",
        quando=has_any_file(COMPOSE_FILES),
        porque="ele declara composição de serviços locais para subir",
    ),
    _agent_doc(
        "mcps",
        "MCPs",
        quando=has_any_file((MCP_CONFIG, MCP_EXAMPLE)),
        porque="ele versiona configuração de MCP, e ninguém sabe quais são sem o documento",
    ),
    AnatomyItem(
        id="triage-vocabulary-declared",
        scope=ORG,
        # Só onde o documento existe: a ausência dele é a linha de `agent-doc-triage-labels`.
        applies=has_file(TRIAGE_DOC),
        satisfied=lambda repo, desired: all(
            role in (repo.content(TRIAGE_DOC) or "") for role in TRIAGE_ROLES
        ),
        motivo=lambda repo, desired: (
            f"{repo.name} tem {TRIAGE_DOC} sem o mapa dos cinco papéis de triagem "
            f"({', '.join(TRIAGE_ROLES)}); o slot é o mapa, e o label de cada papel é escolha "
            "do repo"
        ),
        reads=(TRIAGE_DOC,),
    ),
    AnatomyItem(
        id="no-stale-tool-config",
        scope=ORG,
        applies=always,
        satisfied=lambda repo, desired: not paths_under(repo, STALE_TOOL_CONFIG),
        motivo=lambda repo, desired: (
            f"{repo.name} versiona configuração de ferramenta fora da toolchain decidida: "
            + ", ".join(sorted({p.split("/")[0] for p in paths_under(repo, STALE_TOOL_CONFIG)}))
        ),
    ),
    AnatomyItem(
        id="no-vendored-agent-equipment",
        scope=ORG,
        applies=always,
        satisfied=lambda repo, desired: not paths_under(repo, VENDORED_EQUIPMENT),
        motivo=lambda repo, desired: (
            f"{repo.name} versiona equipamento global, que mora num lugar só: "
            f"{len(paths_under(repo, VENDORED_EQUIPMENT))} arquivo(s), "
            f"a começar por {paths_under(repo, VENDORED_EQUIPMENT)[0]}"
        ),
    ),
    AnatomyItem(
        id="local-commit-gate-exists",
        scope=ORG,
        applies=always,
        satisfied=has_any_file(LOCAL_GATES),
        motivo=lambda repo, desired: (
            f"{repo.name} não declara portão local antes do commit "
            f"({' ou '.join(LOCAL_GATES)}), e erro barato só é pego barato ali"
        ),
    ),
    AnatomyItem(
        id="commit-message-standard-declared",
        scope=ORG,
        applies=always,
        satisfied=any_of(
            has_any_file(COMMIT_LINTERS),
            declares(LOCAL_GATES, ("commitlint",)),
        ),
        motivo=lambda repo, desired: (
            f"{repo.name} não declara o padrão de mensagem de commit em lugar mecânico: "
            "sem configuração de linter de commit nem chamada dele no portão local, o padrão "
            "vive só em prosa"
        ),
        reads=LOCAL_GATES,
    ),
    AnatomyItem(
        id="secret-scan-before-commit",
        scope=ORG,
        # Só onde há portão local: sem ele, a linha a ler é a de `local-commit-gate-exists`.
        applies=has_any_file(LOCAL_GATES),
        satisfied=declares(LOCAL_GATES, (SECRET_SCANNER,)),
        motivo=lambda repo, desired: (
            f"{repo.name} tem portão local que não roda {SECRET_SCANNER}, que é o scanner do "
            "portão de CI: segredo chega ao remoto e só é pego depois do push"
        ),
        reads=LOCAL_GATES,
    ),
    AnatomyItem(
        id="ci-references-shared-workflows",
        scope=ORG,
        applies=always,
        satisfied=lambda repo, desired: (
            SHARED_CI_REF in (repo.content(PR_CHECKS) or "")
            or (repo.tipo == "meta" and LOCAL_CI_REF in (repo.content(PR_CHECKS) or ""))
        ),
        motivo=lambda repo, desired: (
            f"{repo.name} não referencia os workflows compartilhados em {PR_CHECKS}: "
            "os quatro arquivos de CI da frota nasceram copiados um do outro e divergiram entre "
            "48% e 86% em sete semanas, então origem comum não impede deriva"
        ),
        reads=(PR_CHECKS,),
    ),
    AnatomyItem(
        id="status-rollup-contract",
        scope=ORG,
        # Invariante mesmo sem superfície nenhuma: é o rollup que faz a lista fixa
        # de required checks da org sobreviver a stack variável, e sem ele um repo
        # de stack vazia pendura o merge esperando um check que ninguém publica.
        applies=always,
        satisfied=all_of(
            declares((PR_CHECKS,), (job_declared(ROLLUP_CHECK_NAME),)),
            declares((PR_CHECKS,), (job_declared(SECURITY_CHECK_NAME),)),
        ),
        motivo=lambda repo, desired: (
            f"{repo.name} não declara em {PR_CHECKS} os dois jobs de nome fixo do contrato de "
            f"status ({ROLLUP_CHECK_NAME} e {SECURITY_CHECK_NAME}), que são os required checks "
            "da org inteira"
        ),
        reads=(PR_CHECKS,),
    ),
)
