"""Estado de repositório conforme, e as maneiras de tirar uma peça dele.

**As fixtures são estado de repositório, não repositório real.** Os casos que
importam (superfície ausente, tipo não declarado, condicional legitimamente fora
de escopo) são estados que a frota viva não necessariamente está hoje, e amarrar
o teste ao retrato de hoje faria ele mudar de veredito quando alguém consertar um
repositório. Nada aqui toca a rede.

O formato é o **retrato cru**, o mesmo que `fetch_raw` produz e que
`build_observed` consome: assim o teste exercita a conversão junto, e uma mudança
na observação não passa despercebida por uma fixture já interpretada.

`conformant()` devolve um repositório que passa no catálogo **inteiro** para o
tipo e as superfícies pedidas. Cada teste então tira exatamente uma peça e afirma
qual linha aparece. É o que mantém um teste de catálogo legível quando o catálogo
tem trinta itens: o que o teste mostra é a diferença, não o estado todo.
"""

from __future__ import annotations

from typing import Any

from panlabs.checker.model import Observed
from panlabs.checker.observe import build_observed
from panlabs.org.config import load_desired

__all__ = ["conformant", "observed", "without"]

LEFTHOOK = """
pre-commit:
  commands:
    ruff:
      run: uv run ruff check
    biome:
      run: pnpm exec biome check
    gitleaks:
      run: gitleaks protect --staged
commit-msg:
  commands:
    commitlint:
      run: pnpm exec commitlint --edit {1}
"""

PR_CHECKS = """
name: pr-checks
jobs:
  checks-python:
    uses: panlabs-tech/.github/.github/workflows/checks-python.yml@v1.0.0
  checks-node:
    uses: panlabs-tech/.github/.github/workflows/checks-node.yml@v1.0.0
  checks:
    needs: [checks-python, checks-node]
    if: always()
  security:
    uses: panlabs-tech/.github/.github/workflows/security.yml@v1.0.0
"""

TRIAGE_LABELS = """
# Labels de triagem

| Papel canônico | Label no repo |
| --- | --- |
| pronto-para-agente | `dialeto-desta-casa:pronto` |
"""
"""Um dialeto **inventado**, e é de propósito.

Se o catálogo tivesse qualquer dialeto cravado, esta fixture reprovaria. Ela
passar é a prova de que o item lê a declaração e não o valor.
"""

MCP_CONFIG = '{"mcpServers": {"algum": {"env": {"TOKEN": "${ALGUM_TOKEN}"}}}}'

CLAUDE_MD = "@AGENTS.md\n\nO que é genuinamente específico deste agente.\n"


def conformant(
    name: str = "panlabs-tech/fixture",
    *,
    tipo: str | None = None,
    surfaces: tuple[str, ...] = (),
    apps: tuple[str, ...] = ("api", "web"),
    stateful: bool = False,
) -> dict[str, Any]:
    """Um repositório que passa no catálogo inteiro, para aquele tipo e superfícies.

    O nome default não é de repositório da frota de propósito: a descrição e os
    topics governados moram em `config/org.json` por nome, e um nome de lá faria
    a fixture ser cobrada pelo texto exato daquele repositório.
    """
    files = [
        "README.md",
        "LICENSE",
        "AGENTS.md",
        "CLAUDE.md",
        "lefthook.yml",
        ".github/workflows/pr-checks.yml",
        "docs/agents/issue-tracker.md",
        "docs/agents/triage-labels.md",
        "docs/agents/workflow.md",
        "docs/agents/domain.md",
    ]
    contents = {
        "CLAUDE.md": CLAUDE_MD,
        "lefthook.yml": LEFTHOOK,
        ".github/workflows/pr-checks.yml": PR_CHECKS,
        "docs/agents/triage-labels.md": TRIAGE_LABELS,
    }

    if "python" in surfaces:
        files += ["pyproject.toml", ".python-version"]
        contents[".python-version"] = "3.12\n"
    if "node" in surfaces:
        files += ["package.json", ".node-version", "pnpm-lock.yaml"]
        contents[".node-version"] = "22\n"

    if tipo == "meta":
        files.append("ANATOMY.md")
    if tipo == "aplicacao":
        files += [".mcp.json", ".env.example", "pnpm-workspace.yaml"]
        contents[".mcp.json"] = MCP_CONFIG
        for app in apps:
            files += [f"apps/{app}/Dockerfile", f"apps/{app}/README.md"]
        if stateful:
            files += ["apps/api/alembic.ini", "docker-compose.yml"]

    description, topics = _vitrine_of(name)
    return {
        "name": name,
        "tipo": tipo,
        "files": sorted(set(files)),
        "contents": contents,
        "has_readme": True,
        "has_license": True,
        "license": "MIT",
        "description": description,
        "topics": topics,
        "has_wiki": False,
        "private": False,
    }


def _vitrine_of(name: str) -> tuple[str, list[str]]:
    """A descrição e os topics que tornam **este** nome conforme.

    Um repositório governado por `config/org.json` só é conforme com o texto
    exato declarado lá; um fora do dado só precisa ter alguma coisa. Ler o dado
    aqui é o que faz a fixture significar "conforme" em vez de "quase conforme
    para nomes que ninguém governa".
    """
    desired = load_desired()
    descriptions = desired.repo_descriptions or {}
    topics = desired.repo_topics or {}
    return (
        descriptions.get(name, "um repositório de fixture, com descrição"),
        list(topics.get(name, ["python"])),
    )


def without(repo: dict[str, Any], *paths: str) -> dict[str, Any]:
    """O mesmo repositório sem aqueles caminhos, na árvore e no conteúdo lido.

    Tirar de um lugar só produziria um estado que a observação nunca gera: um
    arquivo ausente da árvore não tem conteúdo, e um conteúdo sem árvore é um
    arquivo que a plataforma não listou.
    """
    dropped = set(paths)
    return {
        **repo,
        "files": [path for path in repo["files"] if path not in dropped],
        "contents": {k: v for k, v in repo["contents"].items() if k not in dropped},
    }


def observed(*repos: dict[str, Any]) -> Observed:
    return build_observed({"org": "panlabs-tech", "repos": list(repos)})
