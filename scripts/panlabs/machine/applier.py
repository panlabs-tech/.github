"""Os efeitos da máquina: um ato por ação, e nenhuma decisão.

Cada efeito recebe um item cujo `payload` o planner já montou por inteiro: o alvo
resolvido de uma negação, a forma exata da entrada, o alvo de um link. Nada disso
é recalculado aqui.

**Os efeitos são construídos, não constantes.** `build_effects` recebe o arquivo de
configuração global em que vai escrever, e recebe o mesmo que o observador leu. Um
applier que resolvesse esse endereço por conta própria observaria um arquivo e
escreveria em outro na hora que alguém passasse `--settings`, e escolher onde
escrever é decisão.

As ações de `planner.MANUAL_ACTIONS` não têm efeito registrado, de propósito:
instalar skill é da CLI de distribuição, e remover arquivo versionado de dentro de
um repositório é o retrofit da spec de Repo #4. O planner já as retém. Registrar um
efeito que não deveria rodar seria convidar exatamente o ato que a fronteira entre
as specs proíbe aqui.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from panlabs.machine.planner import DENY_READ, LINK_NAME, PIN_STATUSLINE, RETIRE_DIR
from panlabs.plan import Effect, PlanItem

__all__ = ["build_effects"]


def build_effects(*, settings: Path) -> dict[str, Effect]:
    """A tabela de despacho, amarrada ao arquivo em que ela tem permissão de escrever."""

    def link_name(item: PlanItem) -> None:
        link = Path(item.target)
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(item.payload["target"])

    def retire_dir(item: PlanItem) -> None:
        shutil.rmtree(item.payload["path"], ignore_errors=False)

    def deny_read(item: PlanItem) -> None:
        entry = str(item.payload["entry"])
        _edit(settings, lambda data: _add_deny(data, entry))

    def pin_statusline(item: PlanItem) -> None:
        command = str(item.payload["command"])
        _edit(settings, lambda data: _set_statusline(data, command))

    return {
        LINK_NAME: link_name,
        RETIRE_DIR: retire_dir,
        DENY_READ: deny_read,
        PIN_STATUSLINE: pin_statusline,
    }


def _add_deny(data: dict[str, Any], entry: str) -> None:
    permissions = data.setdefault("permissions", {})
    deny = permissions.setdefault("deny", [])
    if entry not in deny:
        deny.append(entry)


def _set_statusline(data: dict[str, Any], command: str) -> None:
    data["statusLine"] = {"type": "command", "command": command}


def _edit(path: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    """Reescreve a configuração global preservando o que não é do item.

    Reescrever o arquivo inteiro a partir do desejado seria mais simples e apagaria
    chaves que este script não conhece. Ele não é o dono do arquivo, só de duas
    chaves dele.
    """
    data: dict[str, Any] = {}
    if path.exists():
        loaded: Any = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded

    mutate(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
