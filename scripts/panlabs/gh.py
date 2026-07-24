"""Adaptador fino para o `gh` ja autenticado da maquina.

Custo de credencial zero: nada e guardado em lugar nenhum, e nenhuma chamada
daqui decide coisa alguma -- ele so pergunta e responde.

Falha de rede ou de credencial vira `GhError`, e "nao existe" vira `GhNotFoundError`.
A distincao importa: um token expirado nao pode virar "a frota inteira esta fora
do padrao".
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["GhError", "GhNotFoundError", "api", "repo_names"]


class GhError(RuntimeError):
    """O `gh` falhou: rede, credencial, permissao ou resposta inesperada."""


class GhNotFoundError(GhError):
    """O recurso pedido nao existe -- resposta 404, nao falha de infraestrutura."""


def _run(args: Sequence[str]) -> str:
    try:
        completed = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise GhError("o `gh` nao esta instalado ou nao esta no PATH") from exc

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
    """Chama a API do GitHub e devolve a resposta ja desserializada."""
    args = ["api", "--method", method, path]
    if body is not None:
        args += ["--input", "-"]
        return _post_with_body(args, body)

    output = _run(args)
    return json.loads(output) if output.strip() else None


def _post_with_body(args: Sequence[str], body: Mapping[str, Any]) -> Any:
    try:
        completed = subprocess.run(
            ["gh", *args],
            input=json.dumps(body),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GhError("o `gh` nao esta instalado ou nao esta no PATH") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise GhError(f"`gh {' '.join(args)}` falhou: {detail}")

    return json.loads(completed.stdout) if completed.stdout.strip() else None


def repo_names(org: str) -> tuple[str, ...]:
    """Os repos da org viva. Nenhuma contagem, nenhuma lista escrita em codigo."""
    output = _run(["repo", "list", org, "--limit", "1000", "--json", "name", "--jq", ".[].name"])
    return tuple(sorted(name for name in output.split() if name))
