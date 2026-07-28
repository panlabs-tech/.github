"""Os caminhos que mais de um eixo pergunta, escritos num lugar só.

Um módulo de eixo importando outro faria o catálogo ter dependência entre eixos, e
o eixo de um item é justamente o que precisa ficar legível. Mas repetir o caminho
do workflow de PR em dois módulos produziria duas verdades que divergem no dia em
que uma mudar -- e o sintoma seria um item lendo um arquivo que a observação não
busca, isto é, um veredito tirado do vazio.

Os caminhos de manifesto aparecem em plural porque a frota tem mais de um layout.
Todos eles são declarados em `config/checker.json`, e um teste amarra os dois lados:
caminho que um item lê e a observação não busca é caminho que ninguém mede.
"""

from __future__ import annotations

__all__ = [
    "COMPOSE_FILES",
    "LOCAL_CI_REF",
    "MCP_CONFIG",
    "MCP_EXAMPLE",
    "NODE_MANIFESTS",
    "PR_CHECKS",
    "PYTHON_MANIFESTS",
    "SECURITY_SCAN_JOB",
    "SECURITY_WORKFLOW",
    "SHARED_CI_REF",
]

PR_CHECKS = ".github/workflows/pr-checks.yml"
"""O caller de CI de um repositório consumidor: onde a referência compartilhada,
o contrato de nomes de status e as pernas por superfície são todos declarados."""

SHARED_CI_REF = "panlabs-tech/.github/.github/workflows/"
"""A forma versionada com que um consumidor referencia a CI compartilhada."""

LOCAL_CI_REF = "./.github/workflows/"
"""A forma local, válida **só** no repo que publica os workflows compartilhados.

Um caller no mesmo repo sempre resolve contra o próprio SHA, o que evita o
ovo-e-a-galinha de uma tag que ainda não existe no commit que a introduz. Aceitar
esta forma em qualquer repo esvaziaria o item: "referencia workflow local" é
exatamente o que copiar YAML produz.
"""

SECURITY_SCAN_JOB = "security-scan"
SECURITY_WORKFLOW = "security.yml"
"""A única delegação que existe em **todo** repo da frota, com superfície ou sem.

O eixo de stack cobra a perna de cada superfície, e um repo de stack vazia não tem
nenhuma: `panlabs-tech/skills` é o caso vivo. O scan de segurança é o que sobra, e
por isso é ele que o invariante de org verifica. Sem essa âncora, o item de org
não teria o que medir justamente no repositório que serve de fixture para o caso
zero-superfície.
"""

PYTHON_MANIFESTS = ("pyproject.toml", "apps/api/pyproject.toml")
NODE_MANIFESTS = (
    "package.json",
    "apps/web/package.json",
    "web/package.json",
    "scripts/package.json",
)

COMPOSE_FILES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")

MCP_CONFIG = ".mcp.json"
MCP_EXAMPLE = ".mcp.json.example"
"""O exemplo é o padrão atual da frota, e o item que ele aciona não o abençoa.

Um repositório que carrega só o exemplo tem MCP configurado o suficiente para
precisar do documento que explica quais MCPs são aqueles; e continua reprovando no
item que cobra a configuração versionada de verdade. As duas coisas são perguntas
diferentes, e é por isso que são itens diferentes.
"""
