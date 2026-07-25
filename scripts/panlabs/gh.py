"""Adaptador fino para o `gh` já autenticado da máquina.

Custo de credencial zero: nada é guardado em lugar nenhum, e nenhuma chamada
daqui decide coisa alguma: ela só pergunta e responde.

Falha de rede ou de credencial vira `GhError`, e "não existe" vira `GhNotFoundError`.
A distinção importa: um token expirado não pode virar "a frota inteira está fora
do padrão".
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["GhError", "GhNotFoundError", "api", "graphql", "repo_names"]


class GhError(RuntimeError):
    """O `gh` falhou: rede, credencial, permissão ou resposta inesperada."""


class GhNotFoundError(GhError):
    """O recurso pedido não existe: resposta 404, não falha de infraestrutura."""


def _run(args: Sequence[str], *, stdin: str | None = None) -> str:
    """Roda o `gh` e devolve a saída, traduzindo falha em exceção.

    É um caminho só, com ou sem corpo de requisição: duas cópias desta função
    divergiriam justamente no tratamento de erro, que é a razão de ela existir.
    """
    try:
        completed = subprocess.run(
            ["gh", *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GhError("o `gh` não está instalado ou não está no PATH") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        if "HTTP 404" in detail:
            raise GhNotFoundError(detail)
        raise GhError(f"`gh {' '.join(args)}` falhou: {detail}")

    return completed.stdout


def api(
    path: str,
    *,
    method: str = "GET",
    body: Mapping[str, Any] | None = None,
) -> Any:
    """Chama a API do GitHub e devolve a resposta já desserializada."""
    args = ["api", "--method", method, path]
    stdin = None
    if body is not None:
        args += ["--input", "-"]
        stdin = json.dumps(body)

    output = _run(args, stdin=stdin)
    return json.loads(output) if output.strip() else None


def graphql(query: str, **variables: str) -> Any:
    """Consulta a API GraphQL e devolve a resposta já desserializada.

    Existe porque parte do estado da org não tem endpoint REST: os repos fixados
    no perfil, por exemplo, só são legíveis por aqui.
    """
    args = ["api", "graphql", "-f", f"query={query}"]
    for name, value in variables.items():
        args += ["-f", f"{name}={value}"]
    return json.loads(_run(args))


def repo_names(org: str) -> tuple[str, ...]:
    """Os repos da org viva. Nenhuma contagem, nenhuma lista escrita em código."""
    output = _run(["repo", "list", org, "--limit", "1000", "--json", "name", "--jq", ".[].name"])
    return tuple(sorted(name for name in output.split() if name))
