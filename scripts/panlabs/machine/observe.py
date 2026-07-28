"""A fronteira com a máquina viva: lê o sistema de arquivos, decide nada.

O que observar vem do dado desejado, e não de uma varredura do disco inteiro:
não existe "todos os caminhos de credencial da máquina", existe a lista que a
spec decidiu proteger. Observar só o que foi pedido é o que mantém este módulo
sem julgamento.

A única exceção é a varredura de skills, que é genuinamente aberta: a cláusula
de zero redundância afirma algo sobre **todo** repo, então o alvo tem que ser
derivado do disco. Um repo novo com uma cópia nova é exatamente o caso que uma
lista escrita à mão perderia.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from panlabs.machine.config import Desired
from panlabs.machine.model import (
    CredentialPath,
    Link,
    Observed,
    RetireDir,
    Tool,
    VendoredSkill,
)

__all__ = [
    "DEFAULT_AGENT_SETTINGS",
    "DEFAULT_GLOBAL_SKILLS",
    "DEFAULT_WORKSPACES",
    "build_observed",
    "fetch_raw",
    "observed_to_dict",
]

DEFAULT_AGENT_SETTINGS = Path.home() / ".claude" / "settings.json"
DEFAULT_WORKSPACES = Path.home() / "workspaces"

DEFAULT_GLOBAL_SKILLS = (Path.home() / ".agents" / "skills", Path.home() / ".claude" / "skills")
"""Os dois diretórios globais de skill, e ambos contam.

A CLI de distribuição escolhe entre eles conforme instala por link ou por cópia.
Uma medição que conheça só um reporta como ausente uma skill que está instalada, e
o plano então pediria a mesma promoção em toda rodada. "Global" aqui significa
alcançável globalmente, não "mora neste diretório".
"""

VENDOR_DIRS = (".agents/skills", ".claude/skills")
"""Onde uma skill mora dentro de um repo. Os dois, porque um espelha o outro.

O segundo é tipicamente um link para o primeiro; a varredura reporta os dois
endereços porque a cláusula fala de arquivo em repo, e um link versionado
também é arquivo em repo.
"""


def fetch_raw(
    desired: Desired,
    *,
    settings: Path = DEFAULT_AGENT_SETTINGS,
    global_skills: Sequence[Path] = DEFAULT_GLOBAL_SKILLS,
    workspaces: Path = DEFAULT_WORKSPACES,
) -> dict[str, Any]:
    """O retrato cru da máquina, no formato que `build_observed` interpreta."""
    agent = _read_json(settings)
    permissions = agent.get("permissions") or {}
    statusline = agent.get("statusLine") or {}

    return {
        "links": [_look_at_link(desired.bin_dir, link.name) for link in desired.links or ()],
        "retire": [_look_at_dir(entry.path) for entry in desired.retire or ()],
        "credentials": [_look_at_secret(entry.path) for entry in desired.read_denylist or ()],
        "denylist": [str(rule) for rule in permissions.get("deny") or ()],
        "statusline": str(statusline.get("command") or ""),
        "global_skills": sorted({name for root in global_skills for name in _names_in(root)}),
        "vendored_skills": _scan_vendored(workspaces),
        "tools": [_look_at_tool(tool.name) for tool in desired.tools or ()],
    }


def _look_at_tool(name: str) -> dict[str, Any]:
    """Onde este nome resolve, ou vazio.

    Por `which`, e não pela existência de um arquivo no diretório de binários: o
    que se pergunta aqui é se a ferramenta é **alcançável pelo nome**, e o método
    de instalação dela decide onde ela mora. Um `gitleaks` que o gerenciador de
    pacotes tivesse posto em `/usr/bin` satisfaz o invariante do mesmo jeito.

    Alias de shell não aparece aqui, pelo mesmo motivo de `_look_at_link`: alias
    não existe em subprocesso, que é como o agente roda.
    """
    return {"name": name, "resolved": shutil.which(name) or ""}


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, Mapping) else {}


def _look_at_link(bin_dir: str | None, name: str) -> dict[str, Any]:
    """Onde este nome resolve hoje, se resolve.

    Um alias de shell nunca aparece aqui, e isso é o ponto: alias não existe em
    subprocesso, que é como o agente roda, então para esta medição ele é ausência.
    """
    if bin_dir is None:
        return {"name": name, "points_to": "", "resolved": ""}
    candidate = Path(bin_dir) / name
    if not candidate.exists() and not candidate.is_symlink():
        return {"name": name, "points_to": "", "resolved": ""}
    points_to = os.readlink(candidate) if candidate.is_symlink() else str(candidate)
    return {
        "name": name,
        "points_to": points_to,
        "resolved": str(candidate.resolve()),
        "anchored_target": candidate.is_symlink() and _anchors_on_own_dir(candidate.resolve()),
    }


ANCHOR_MARKS = ('dirname "$0"', "dirname $0", "dirname `$0`", "dirname '$0'")
"""Como um shim escreve "o diretório onde eu mesmo estou".

A medição é por leitura, nunca por execução: um binário de barra de status
invocado sem argumento abre uma interface interativa, e uma observação que o
executasse travaria a medição da máquina inteira.
"""


def _anchors_on_own_dir(target: Path) -> bool:
    """Se este alvo só funciona no diretório dele, e por isso quebra sob link.

    O defeito que originou esta medição: o shim do pacote calculava o caminho do
    que executar a partir de `dirname $0` e o compunha com `..`. Alcançado pelo
    link em `bin_dir`, ele passou a procurar o pacote ao lado do link, e o nome
    morria com `MODULE_NOT_FOUND` mesmo apontando para onde o dado pedia.

    Só script conta. Um shim compilado resolve o que executar pelo nome com que
    foi invocado, não pelo diretório em que mora, e sobrevive ao link: é o caso
    dos shims do gerenciador de runtime, que são binário.
    """
    try:
        head = target.read_bytes()[:4096]
    except OSError:
        return False
    if not head.startswith(b"#!"):
        return False
    text = head.decode("utf-8", errors="replace")
    return any(mark in text for mark in ANCHOR_MARKS) and "/.." in text


def _look_at_dir(path: str) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"path": path, "present": False, "bytes": 0}
    return {"path": path, "present": True, "bytes": _size_of(target)}


def _size_of(root: Path) -> int:
    """Soma o tamanho aparente, sem seguir link, porque link não ocupa o alvo."""
    total = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d))]
        for name in files:
            entry = os.path.join(base, name)
            if os.path.islink(entry):
                continue
            try:
                total += os.path.getsize(entry)
            except OSError:
                continue
    return total


def _look_at_secret(path: str) -> dict[str, Any]:
    """Como o caminho foi escrito, onde ele resolve, e quanto guarda hoje.

    `resolved` é o campo que carrega a decisão desta issue: negar o nome escrito
    bloqueia a ferramenta e deixa o shell passar, porque o shell fala com o alvo.
    """
    target = Path(path)
    if not target.exists():
        return {"path": path, "present": False, "resolved": "", "is_dir": True, "entries": 0}

    resolved = target.resolve()
    is_dir = resolved.is_dir()
    return {
        "path": path,
        "present": True,
        "resolved": str(resolved),
        "is_dir": is_dir,
        "entries": len(list(resolved.iterdir())) if is_dir else 1,
    }


def _names_in(root: Path) -> Iterable[str]:
    if not root.is_dir():
        return ()
    return (entry.name for entry in root.iterdir() if not entry.name.startswith("."))


def _scan_vendored(workspaces: Path) -> list[dict[str, Any]]:
    """Toda skill que mora dentro de um repo, derivada do disco.

    Dois níveis, e o segundo não é zelo: o layout que a issue #21 impõe põe **todo
    repo da org** sob um diretório que espelha o nome da org, um nível mais fundo
    que os repos pessoais. Varrer só um nível deixaria a cláusula de zero
    redundância cega justamente na metade da frota que é da org.

    O repo meta da org tem nome começando por ponto, então um glob ingênuo o
    perderia para sempre. `iterdir` não filtra oculto, e é por isso que ele está
    aqui em vez de um padrão com asterisco.
    """
    if not workspaces.is_dir():
        return []

    found: list[dict[str, Any]] = []
    for repo in _candidate_repos(workspaces):
        for vendor in VENDOR_DIRS:
            for skill in sorted(_names_in(repo / vendor)):
                found.append(
                    {
                        "repo": str(repo.relative_to(workspaces)),
                        "name": skill,
                        "path": str(repo / vendor / skill),
                    }
                )
    return found


SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "__pycache__"})
"""Diretórios que a varredura nunca entra, porque não são fonte versionada.

Um artefato reproduzível pode carregar um diretório de skill de dentro de um
pacote instalado, e contá-lo inflaria a redundância com algo que nem é do repo.
"""


def _candidate_repos(workspaces: Path) -> list[Path]:
    """Os diretórios que podem carregar skill: os filhos, e os netos deles.

    Um diretório é reportado como repo **e** varrido por dentro, sem escolher entre
    as duas coisas: adivinhar qual dos dois um diretório é exigiria decidir o que é
    repo e o que é agrupador, e essa decisão não é da observação.

    **Dois níveis, e o limite é deliberado.** Dois cobrem os dois layouts que
    existem: repo pessoal no primeiro nível, repo da org sob o diretório que
    espelha a org, no segundo. Descer mais alcançaria worktree aninhada dentro de um
    repo, e a cópia que ela carrega é **o mesmo arquivo versionado** do repo pai,
    já contado uma vez ali. Contá-la de novo faria a redundância parecer maior do
    que ela é, e podar worktree é da issue #21.
    """
    candidates: list[Path] = []
    for child in _children(workspaces):
        candidates.append(child)
        candidates.extend(_children(child))
    return candidates


def _children(root: Path) -> list[Path]:
    return [
        entry
        for entry in sorted(root.iterdir())
        if entry.is_dir() and not entry.is_symlink() and entry.name not in SKIP_DIRS
    ]


def build_observed(raw: Mapping[str, Any]) -> Observed:
    """Do JSON cru para o tipo que o planner recebe. Sem julgamento nenhum."""
    return Observed(
        links=tuple(
            Link(
                name=entry["name"],
                points_to=entry.get("points_to", ""),
                resolved=entry.get("resolved", ""),
                anchored_target=bool(entry.get("anchored_target")),
            )
            for entry in raw.get("links") or ()
        ),
        retire=tuple(
            RetireDir(
                path=entry["path"],
                present=bool(entry.get("present")),
                bytes=int(entry.get("bytes") or 0),
            )
            for entry in raw.get("retire") or ()
        ),
        credentials=tuple(
            CredentialPath(
                path=entry["path"],
                present=bool(entry.get("present")),
                resolved=entry.get("resolved", ""),
                is_dir=bool(entry.get("is_dir", True)),
                entries=int(entry.get("entries") or 0),
            )
            for entry in raw.get("credentials") or ()
        ),
        denylist=tuple(raw.get("denylist") or ()),
        statusline=raw.get("statusline") or "",
        global_skills=tuple(raw.get("global_skills") or ()),
        vendored_skills=tuple(
            VendoredSkill(repo=entry["repo"], name=entry["name"], path=entry["path"])
            for entry in raw.get("vendored_skills") or ()
        ),
        tools=tuple(
            Tool(name=entry["name"], resolved=entry.get("resolved", ""))
            for entry in raw.get("tools") or ()
        ),
    )


def observed_to_dict(observed: Observed) -> dict[str, Any]:
    """O retrato observado, de volta a JSON legível. Igual aos subpacotes irmãos."""
    return {
        "links": [
            {
                "name": x.name,
                "points_to": x.points_to,
                "resolved": x.resolved,
                "anchored_target": x.anchored_target,
            }
            for x in observed.links
        ],
        "retire": [
            {"path": x.path, "present": x.present, "bytes": x.bytes} for x in observed.retire
        ],
        "credentials": [
            {
                "path": x.path,
                "present": x.present,
                "resolved": x.resolved,
                "is_dir": x.is_dir,
                "entries": x.entries,
            }
            for x in observed.credentials
        ],
        "denylist": list(observed.denylist),
        "statusline": observed.statusline,
        "global_skills": list(observed.global_skills),
        "vendored_skills": [
            {"repo": x.repo, "name": x.name, "path": x.path} for x in observed.vendored_skills
        ],
        "tools": [{"name": x.name, "resolved": x.resolved} for x in observed.tools],
    }
