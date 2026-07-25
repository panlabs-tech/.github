"""Os efeitos da máquina: um ato por ação, e nenhuma decisão.

Cada efeito recebe um item cujo `payload` o planner já montou por inteiro. O alvo
resolvido de uma negação, a forma exata da entrada, o alvo de um link: tudo isso
já foi decidido antes de chegar aqui.

As ações de `planner.MANUAL_ACTIONS` não têm efeito registrado, de propósito:
remover arquivo versionado de dentro de um repositório é o retrofit da spec de
Repo #4, e o planner já as retém. Registrar um efeito que não deveria rodar seria
convidar exatamente a remoção que a fronteira entre as specs proíbe aqui.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from panlabs.machine.planner import DENY_READ, LINK_NAME, PIN_STATUSLINE, PROMOTE_SKILL, RETIRE_DIR
from panlabs.plan import Effect, PlanItem

__all__ = ["EFFECTS", "settings_path", "skills_paths"]

_SETTINGS = Path.home() / ".claude" / "settings.json"
_GLOBAL_SKILLS = Path.home() / ".agents" / "skills"
_AGENT_SKILLS = Path.home() / ".claude" / "skills"


def settings_path() -> Path:
    return _SETTINGS


def skills_paths() -> tuple[Path, Path]:
    return _GLOBAL_SKILLS, _AGENT_SKILLS


def _link_name(item: PlanItem) -> None:
    link = Path(item.target)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(item.payload["target"])


def _retire_dir(item: PlanItem) -> None:
    shutil.rmtree(item.payload["path"], ignore_errors=False)


def _deny_read(item: PlanItem) -> None:
    _edit_settings(lambda data: _add_deny(data, str(item.payload["entry"])))


def _pin_statusline(item: PlanItem) -> None:
    _edit_settings(lambda data: _set_statusline(data, str(item.payload["command"])))


def _promote_skill(item: PlanItem) -> None:
    """Copia a skill para o global e a torna visível ao agente pelo link nativo."""
    global_skills, agent_skills = skills_paths()
    global_skills.mkdir(parents=True, exist_ok=True)
    agent_skills.mkdir(parents=True, exist_ok=True)

    name = str(item.payload["name"])
    destination = global_skills / name
    if not destination.exists():
        shutil.copytree(item.payload["from"], destination, symlinks=True)

    link = agent_skills / name
    if not link.is_symlink() and not link.exists():
        link.symlink_to(destination)


def _add_deny(data: dict[str, Any], entry: str) -> None:
    permissions = data.setdefault("permissions", {})
    deny = permissions.setdefault("deny", [])
    if entry not in deny:
        deny.append(entry)


def _set_statusline(data: dict[str, Any], command: str) -> None:
    data["statusLine"] = {"type": "command", "command": command}


def _edit_settings(mutate: Any) -> None:
    """Reescreve o arquivo de configuração global preservando o que não é do item.

    Reescrever o arquivo inteiro a partir do desejado seria mais simples e apagaria
    chaves que este script não conhece. Ele não é o dono do arquivo, só de duas
    chaves dele.
    """
    path = settings_path()
    data: dict[str, Any] = {}
    if path.exists():
        loaded: Any = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded

    mutate(data)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


EFFECTS: dict[str, Effect] = {
    LINK_NAME: _link_name,
    RETIRE_DIR: _retire_dir,
    DENY_READ: _deny_read,
    PIN_STATUSLINE: _pin_statusline,
    PROMOTE_SKILL: _promote_skill,
}
