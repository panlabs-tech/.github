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
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from panlabs.machine.config import Desired
from panlabs.machine.model import CredentialPath, Link, Observed, RetireDir, VendoredSkill

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
    }


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
    }


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

    O repo meta da org tem nome começando por ponto, então um glob ingênuo o
    perderia para sempre. `iterdir` não filtra oculto, e é por isso que ele está
    aqui em vez de um padrão com asterisco.
    """
    if not workspaces.is_dir():
        return []

    found: list[dict[str, Any]] = []
    for repo in sorted(workspaces.iterdir()):
        if not repo.is_dir():
            continue
        for vendor in VENDOR_DIRS:
            for skill in sorted(_names_in(repo / vendor)):
                found.append({"repo": repo.name, "name": skill, "path": str(repo / vendor / skill)})
    return found


def build_observed(raw: Mapping[str, Any]) -> Observed:
    """Do JSON cru para o tipo que o planner recebe. Sem julgamento nenhum."""
    return Observed(
        links=tuple(
            Link(
                name=entry["name"],
                points_to=entry.get("points_to", ""),
                resolved=entry.get("resolved", ""),
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
    )


def observed_to_dict(observed: Observed) -> dict[str, Any]:
    return observed.to_dict()
