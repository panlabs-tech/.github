"""Adaptador fino para o `gh` já autenticado da máquina.

Custo de credencial zero: nada é guardado em lugar nenhum, e nenhuma chamada
daqui decide coisa alguma: ela só pergunta e responde.

Falha de rede ou de credencial vira `GhError`, e "não existe" vira `GhNotFoundError`.
A distinção importa: um token expirado não pode virar "a frota inteira está fora
do padrão".

Pelo mesmo motivo, um 403 também não é um só. "Este plano não oferece rulesets
em repositório privado" é uma resposta sobre o que a plataforma **mostra**, e
some quando o repo vira público; "eleve o token" é falta de permissão, e some
quando o operador eleva o escopo. Os dois chegam com o mesmo código HTTP, e só
o texto da plataforma os separa.

E o `gh` é invocado por **caminho**, nunca por nome nu. Quem chama este módulo
sem terminal roda com o PATH mínimo do sistema, onde o instalador por usuário
não está.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "GhError",
    "GhNotFoundError",
    "GhUpgradeRequiredError",
    "api",
    "binary",
    "graphql",
    "repo_names",
]

USER_BIN_DIRS = ("~/.local/bin", "~/bin")
"""Onde procurar o `gh` quando o PATH herdado não o alcança.

O `PATH` de um subprocesso não interativo é o mínimo do sistema: sem arquivo de
rc, sem o que o shell de login acrescenta, e portanto sem o diretório em que
`gh` é instalado por usuário. Um `gh` que responde a `command -v` no terminal e
some na tarefa agendada é o mesmo binário visto de dois ambientes, e é essa
diferença que manteve o passo `anatomy-checker` do heartbeat sem produzir uma
matriz desde que ele existe.

A lista é curta e escrita aqui de propósito. Ler `config/machine.json` daqui
inverteria a dependência: este adaptador serve o checker, o ruleset e o script
de org, que rodam também onde não existe máquina panlabs nenhuma. O que amarra
os dois lados é um teste, e ele falha se `bin_dir` sair desta lista.
"""

UPGRADE_MARKER = "Upgrade to GitHub"
"""O que o GitHub diz quando o plano da conta não oferece o recurso pedido.

Acoplar ao texto da plataforma tem custo, e ele é pago de propósito: é a única
coisa que distingue os dois 403, e sem a distinção o motivo escrito no plano
mentiria em metade dos casos. O acoplamento é **fail-closed**, e é isso que o
torna aceitável: se o GitHub reescrever a frase, este ramo deixa de casar e a
falha volta a ser o `GhError` fatal de sempre. O desenho erra para o lado
barulhento, nunca para o silencioso.

Só o prefixo, sem a edição do plano: "Upgrade to GitHub Pro" hoje, e o dia em
que uma dimensão exigir Team ou Enterprise não deve precisar de outra linha aqui.
"""


GH = "gh"
"""O nome do executável, num lugar só: ele é procurado e é invocado."""


class GhError(RuntimeError):
    """O `gh` falhou: rede, credencial, permissão ou resposta inesperada."""


class GhNotFoundError(GhError):
    """O recurso pedido não existe: resposta 404, não falha de infraestrutura."""


class GhUpgradeRequiredError(GhError):
    """A plataforma recusou por plano ou visibilidade, não por falta de permissão.

    Nenhum token conserta este: o recurso existe, e o repositório é que não o
    alcança onde está. É a única classe de recusa que quem observa pode tratar
    como fato sobre o alvo em vez de falha da corrida, e por isso ela é estreita
    de propósito. Continua sendo `GhError`: quem só sabe capturar o pai continua
    capturando este, e para de graça.
    """


def binary() -> str:
    """O caminho do `gh` desta máquina, ou o nome nu se ele não for encontrado.

    O PATH manda quando responde: quem tem ambiente bom continua usando o `gh` que
    escolheu, e esta busca não sequestra nada. Só quando ele não responde é que os
    diretórios de instalação por usuário são consultados, na ordem escrita.

    Devolver o nome nu no fim é deliberado, e não é desistência: ele reproduz o
    `FileNotFoundError` de sempre, que vira o erro alto e legível de `_run`. A
    degradação é barulhenta, nunca silenciosa: um `gh` que de fato não existe
    continua derrubando a corrida, e é o texto do erro que ganha o endereço.
    """
    found = shutil.which(GH)
    if found:
        return found
    for directory in USER_BIN_DIRS:
        candidate = Path(directory).expanduser() / GH
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return GH


def _run(args: Sequence[str], *, stdin: str | None = None) -> str:
    """Roda o `gh` e devolve a saída, traduzindo falha em exceção.

    É um caminho só, com ou sem corpo de requisição: duas cópias desta função
    divergiriam justamente no tratamento de erro, que é a razão de ela existir.
    """
    try:
        completed = subprocess.run(
            [binary(), *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GhError(
            "o `gh` não está instalado, não está no PATH e não está em "
            f"{' nem em '.join(USER_BIN_DIRS)}"
        ) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        if "HTTP 404" in detail:
            raise GhNotFoundError(detail)
        if "HTTP 403" in detail and UPGRADE_MARKER in detail:
            raise GhUpgradeRequiredError(detail)
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
