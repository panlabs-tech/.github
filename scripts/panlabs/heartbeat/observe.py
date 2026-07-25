"""A fronteira com a máquina viva e com o host. Lê; decide nada.

Três medições, e cada uma tem um motivo de estar aqui e não no planner:

**O ramo, consultado sem bootar nada.** `wsl.exe --list --running --quiet` só
lista; ele não sobe distro e não derruba nenhuma. A consulta é a única coisa que a
tarefa faz antes de saber em que estado a máquina está, e ela precisa ser inócua:
o desenho inteiro promete nunca ligar, nunca desligar e nunca interromper trabalho.

**O disco do host, que não existe de dentro.** O disco virtual é
*thin-provisioned* e declara um teto de 1 TB; o `df` de dentro reporta centenas de
GB que fisicamente não estão em lugar nenhum. Só o host enxerga os bytes reais, e é
por isso que essa medição atravessa a fronteira em vez de sair de `statvfs`.

**As marcas, que moram do lado do host.** É o único lado que as enxerga com o WSL
parado, que é justamente o estado em que o ramo de compactação existe. Dentro do
WSL elas são alcançadas pelo caminho estável de estado, que o script de
reconciliação aponta para o lado de lá.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from panlabs.heartbeat.config import Desired
from panlabs.heartbeat.model import CacheVersion, HostDisk, LeftoverFile, Mark, Observed

__all__ = [
    "DEFAULT_STATE_DIR",
    "HOST_DISK_QUERY",
    "MARKS_FILE",
    "SCAN_DEPTH",
    "WSL_QUERY",
    "build_observed",
    "fetch_raw",
    "observed_to_dict",
    "read_marks",
    "scan_leftovers",
    "scan_versions",
]

DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "panlabs" / "heartbeat"
"""O caminho estável de estado dentro do WSL.

Ele é um link para o diretório do lado do host, criado pelo script de
reconciliação dos dotfiles. A indireção existe para que nada aqui precise
descobrir o nome de usuário do Windows a cada execução, e para que o vigia de
homem-morto no shell leia a mesma marca por um caminho barato.
"""

MARKS_FILE = "marks.json"

WSL_QUERY = ("wsl.exe", "--list", "--running", "--quiet")
"""A consulta de ramo, e ela é inócua por construção.

Nenhuma outra forma serve: `--list` sozinho não diz quem está de pé, e qualquer
comando com `-d` ou `--exec` **subiria** a distro, que é exatamente o ato que
transformaria uma consulta num boot. `--shutdown` e `--terminate` não aparecem em
lugar nenhum deste repo, e um teste guarda essa ausência.
"""

HOST_DISK_QUERY = (
    "powershell.exe",
    "-NoProfile",
    "-NonInteractive",
    "-Command",
    '$d = Get-PSDrive C; [Console]::Out.Write("$($d.Free) $($d.Used)")',
)

SCAN_DEPTH = 2
"""Quantos níveis a varredura de cache versionado desce, e o limite é deliberado.

Dois cobrem os dois layouts que existem: um cache que versiona na raiz
(`ms-playwright/chromium-1223`) e um que versiona por produto
(`puppeteer/chrome/linux-148.0.7778.97`). Descer mais alcançaria o conteúdo do
próprio browser, onde não há revisão nenhuma para comparar.
"""

VERSIONED = re.compile(r"^(?P<prefix>.+?)-(?P<version>\d+(?:\.\d+)*)$")
"""`chromium-1223`, `chromium_headless_shell-1169`, `linux-148.0.7778.97`.

Um diretório que não casa não é revisão de nada: é agrupador, e a varredura desce
por dentro dele em vez de o tratar como candidato à poda.
"""


def fetch_raw(desired: Desired, *, state_dir: Path = DEFAULT_STATE_DIR) -> dict[str, Any]:
    """O retrato cru, no formato que `build_observed` interpreta."""
    marks = read_marks(state_dir)
    free, used = _host_disk()

    return {
        "now": datetime.now(UTC).isoformat(),
        "wsl_running": _wsl_running(),
        "host": {
            "measured": free is not None,
            "free_bytes": free or 0,
            "total_bytes": (free + used) if free is not None and used is not None else 0,
        },
        "last_run": marks.get("last_run"),
        "marks": [
            {"step": step, "at": at} for step, at in sorted((marks.get("steps") or {}).items())
        ],
        "versions": scan_versions(_roots(desired, "keep_newest")),
        "leftovers": scan_leftovers(desired),
    }


def read_marks(state_dir: Path) -> dict[str, Any]:
    """As marcas gravadas, ou um retrato vazio. Ausente é o primeiro disparo.

    A leitura é `utf-8-sig` porque **este arquivo tem dois autores**, e um deles é
    o script do host: o PowerShell do Windows grava UTF-8 com marca de ordem de
    bytes, e o leitor de JSON do Python recusa essa marca. Lido como `utf-8`, o
    arquivo escrito pelo host viraria "primeiro disparo" em toda execução, o que
    apagaria a cadência de todos os passos e mataria o alarme de marca velha em
    silêncio. Medido, não deduzido: aconteceu na primeira execução de ponta a ponta.
    """
    path = state_dir / MARKS_FILE
    if not path.exists():
        return {}
    try:
        loaded: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


# --- o ramo, sem bootar nada --------------------------------------------------


def _wsl_running() -> bool | None:
    """De pé, parado, ou **não consultado**. O terceiro não é o segundo.

    Uma consulta que falhou não pode virar "parado": o ramo parado é o que roda a
    compactação, e compactar um disco vivo é o único desastre que este desenho
    tem como causar. Sem resposta, o planner não planeja passo nenhum e o operador
    é notificado.
    """
    out = _capture(WSL_QUERY)
    if out is None:
        return None
    return bool(out.strip())


def _host_disk() -> tuple[int | None, int | None]:
    out = _capture(HOST_DISK_QUERY)
    if out is None:
        return None, None
    parts = out.split()
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def _capture(command: Sequence[str]) -> str | None:
    """Roda um comando do host e devolve a saída, ou `None` se ela não veio.

    As ferramentas do host respondem em UTF-16, e `errors="replace"` existe para
    que uma resposta com byte inesperado vire texto ruim em vez de exceção: o que
    o chamador precisa distinguir é "não respondeu" de "respondeu", e uma decodificação
    estrita transformaria as duas na mesma coisa.
    """
    try:
        done = subprocess.run(command, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return _decode(done.stdout)


def _decode(raw: bytes) -> str:
    if b"\x00" in raw:
        return raw.decode("utf-16-le", errors="replace").replace("﻿", "")
    return raw.decode("utf-8", errors="replace")


# --- os caches versionados, e os órfãos --------------------------------------


def _roots(desired: Desired, body: str) -> list[str]:
    """As raízes que o dado desejado mandou olhar. Nenhuma varredura é do disco todo."""
    seen: list[str] = []
    for step in desired.steps or ():
        wanted = getattr(step, body)
        if wanted is not None and wanted.root not in seen:
            seen.append(wanted.root)
    return seen


def scan_versions(roots: Iterable[str]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for entry, family, version in _versioned_dirs(base, base, SCAN_DEPTH):
            found.append(
                {
                    "root": root,
                    "family": family,
                    "version": list(version),
                    "path": str(entry),
                    "bytes": _size_of(entry),
                }
            )
    return sorted(found, key=lambda entry: entry["path"])


def _versioned_dirs(
    base: Path, current: Path, depth: int
) -> list[tuple[Path, str, tuple[int, ...]]]:
    """Os diretórios que são revisão, e nunca o que está dentro de uma revisão.

    Uma revisão não é varrida por dentro: o que ela guarda é o browser, e ali não
    existe versão a comparar. Um diretório que não é revisão é agrupador, e é por
    dentro dele que a família de um produto aparece.
    """
    if depth <= 0:
        return []

    found: list[tuple[Path, str, tuple[int, ...]]] = []
    for entry in sorted(_children(current)):
        matched = VERSIONED.match(entry.name)
        if matched is None:
            found.extend(_versioned_dirs(base, entry, depth - 1))
            continue
        found.append((entry, _family(base, entry, matched.group("prefix")), _version(matched)))
    return found


def _family(base: Path, entry: Path, prefix: str) -> str:
    """O produto a que esta revisão pertence, com o caminho até ele.

    Sem o caminho, `chrome/linux-148` e `chrome-headless-shell/linux-127` seriam a
    mesma família `linux`, e a poda apagaria o browser atual de um dos dois.
    """
    parent = entry.parent.relative_to(base).as_posix()
    return prefix if parent == "." else f"{parent}/{prefix}"


def _version(matched: re.Match[str]) -> tuple[int, ...]:
    return tuple(int(part) for part in matched.group("version").split("."))


def scan_leftovers(desired: Desired) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for step in desired.steps or ():
        wanted = step.drop_matching
        if wanted is None:
            continue
        base = Path(wanted.root)
        if not base.is_dir():
            continue
        for entry in _files_ending(base, wanted.suffix, SCAN_DEPTH):
            found.append({"root": wanted.root, "path": str(entry), "bytes": _file_size(entry)})
    return sorted(found, key=lambda entry: entry["path"])


def _files_ending(current: Path, suffix: str, depth: int) -> list[Path]:
    if depth <= 0:
        return []
    found: list[Path] = []
    for entry in sorted(current.iterdir()):
        if entry.is_symlink():
            continue
        if entry.is_dir():
            found.extend(_files_ending(entry, suffix, depth - 1))
        elif entry.name.endswith(suffix):
            found.append(entry)
    return found


def _children(root: Path) -> list[Path]:
    return [entry for entry in root.iterdir() if entry.is_dir() and not entry.is_symlink()]


def _size_of(root: Path) -> int:
    """Soma o tamanho aparente, sem seguir link, porque link não ocupa o alvo."""
    total = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d))]
        for name in files:
            total += _file_size(Path(base) / name)
    return total


def _file_size(entry: Path) -> int:
    if entry.is_symlink():
        return 0
    try:
        return entry.stat().st_size
    except OSError:
        return 0


# --- do cru para o tipo, e de volta ------------------------------------------


def build_observed(raw: Mapping[str, Any]) -> Observed:
    """Do JSON cru para o tipo que o planner recebe. Sem julgamento nenhum."""
    host = raw.get("host") or {}
    return Observed(
        now=_moment(raw.get("now")) or datetime.now(UTC),
        wsl_running=_tristate(raw.get("wsl_running")),
        host=HostDisk(
            measured=bool(host.get("measured")),
            free_bytes=int(host.get("free_bytes") or 0),
            total_bytes=int(host.get("total_bytes") or 0),
        ),
        last_run=_moment(raw.get("last_run")),
        marks=tuple(
            Mark(step=entry["step"], at=_moment(entry.get("at")))
            for entry in raw.get("marks") or ()
        ),
        versions=tuple(
            CacheVersion(
                root=entry["root"],
                family=entry["family"],
                version=tuple(int(part) for part in entry["version"]),
                path=entry["path"],
                bytes=int(entry.get("bytes") or 0),
            )
            for entry in raw.get("versions") or ()
        ),
        leftovers=tuple(
            LeftoverFile(root=entry["root"], path=entry["path"], bytes=int(entry.get("bytes") or 0))
            for entry in raw.get("leftovers") or ()
        ),
    )


def _tristate(value: Any) -> bool | None:
    """`None` é "não consultado", e ele nunca colapsa em `False`."""
    return None if value is None else bool(value)


def _moment(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))


def observed_to_dict(observed: Observed) -> dict[str, Any]:
    """O retrato observado, de volta a JSON legível. Igual aos subpacotes irmãos."""
    return {
        "now": observed.now.isoformat(),
        "wsl_running": observed.wsl_running,
        "host": {
            "measured": observed.host.measured,
            "free_bytes": observed.host.free_bytes,
            "total_bytes": observed.host.total_bytes,
        },
        "last_run": observed.last_run.isoformat() if observed.last_run else None,
        "marks": [
            {"step": x.step, "at": x.at.isoformat() if x.at else None} for x in observed.marks
        ],
        "versions": [
            {
                "root": x.root,
                "family": x.family,
                "version": list(x.version),
                "path": x.path,
                "bytes": x.bytes,
            }
            for x in observed.versions
        ],
        "leftovers": [
            {"root": x.root, "path": x.path, "bytes": x.bytes} for x in observed.leftovers
        ],
    }
