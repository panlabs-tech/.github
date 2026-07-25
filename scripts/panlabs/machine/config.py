"""A configuração desejada da máquina: dado versionado, carregado de arquivo.

Os valores são decididos pela spec de Máquina #3 e vivem em `config/machine.json`.
Este módulo entrega o esqueleto do dado e a sua leitura, nunca os valores.

Uma chave ausente ou nula significa **ainda não decidido**, e o planner não
planeja nada para a dimensão correspondente. Isso é diferente de "decidido como
vazio": `retire: []` é uma decisão, `null` não é.

Os caminhos entram no dado com `~`, porque é assim que um humano os revisa, e
saem daqui absolutos, porque é assim que o planner os compara. Expandir na
leitura é deliberado: o dado é o mesmo em qualquer máquina, a expansão é local.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "Desired",
    "DesiredLink",
    "DesiredRetire",
    "DesiredSecret",
    "DesiredSkills",
    "SkillMove",
    "expand",
    "load_desired",
]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "machine.json"

KNOWN_KEYS = ("bin_dir", "links", "retire", "read_denylist", "statusline", "skills")


def expand(path: str) -> str:
    """`~/x` vira o caminho absoluto desta máquina, sem resolver link nenhum.

    Resolver link aqui seria errado: qual caminho é link e para onde ele aponta é
    **observação**, e a decisão de negar o alvo em vez do nome escrito é do
    planner. Este módulo só transforma dado em endereço.
    """
    return str(Path(path).expanduser())


@dataclass(frozen=True)
class DesiredLink:
    """Um nome que precisa resolver num alvo, e o motivo de ele existir."""

    name: str
    target: str
    why: str


@dataclass(frozen=True)
class DesiredRetire:
    """Um diretório cuja remoção está decidida, com o motivo escrito."""

    path: str
    why: str


@dataclass(frozen=True)
class DesiredSecret:
    """Um lugar de credencial que a leitura do agente não deve alcançar."""

    path: str
    why: str


@dataclass(frozen=True)
class SkillMove:
    """Uma skill que sai de um repo: promovida ao global ou descartada.

    `superseded_by` preenchido é o que separa descarte de promoção: uma skill que
    é revisão antiga de uma global já existente não sobe, porque subir criaria
    duas globais para o mesmo trabalho, que é a redundância que a cláusula proíbe.
    """

    name: str
    source: str
    why: str
    superseded_by: str = ""


@dataclass(frozen=True)
class DesiredSkills:
    """A cláusula de zero redundância, como dado.

    Só o lado global entra aqui, porque só ele é desta issue: promover as órfãs
    reais e registrar quais cópias são revisão antiga de uma global existente. A
    varredura que prova a cláusula é do planner, e o que ela encontra dentro dos
    repos é **retido**, porque remover arquivo versionado de um repositório é o
    retrofit da spec de Repo #4.
    """

    promote: tuple[SkillMove, ...] = ()
    discard: tuple[SkillMove, ...] = ()


@dataclass(frozen=True)
class Desired:
    """O estado desejado do equipamento da máquina."""

    bin_dir: str | None = None
    links: tuple[DesiredLink, ...] | None = None
    retire: tuple[DesiredRetire, ...] | None = None
    read_denylist: tuple[DesiredSecret, ...] | None = None
    statusline: str | None = None
    skills: DesiredSkills | None = None

    @property
    def undecided(self) -> tuple[str, ...]:
        """As dimensões que ainda esperam decisão da spec de Máquina #3."""
        return tuple(sorted(key for key in KNOWN_KEYS if getattr(self, key) is None))

    @property
    def is_decided(self) -> bool:
        return not self.undecided

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Desired:
        unknown = sorted(k for k in raw if not k.startswith("_") and k not in KNOWN_KEYS)
        if unknown:
            raise ValueError(
                f"chave desconhecida na configuração desejada: {', '.join(unknown)}; "
                f"chaves válidas: {', '.join(KNOWN_KEYS)}"
            )

        return cls(
            bin_dir=_maybe_expand(raw.get("bin_dir")),
            links=_links(raw.get("links")),
            retire=_retire(raw.get("retire")),
            read_denylist=_secrets(raw.get("read_denylist")),
            statusline=raw.get("statusline"),
            skills=_skills(raw.get("skills")),
        )


def _maybe_expand(value: Any) -> str | None:
    return None if value is None else expand(str(value))


def _require(entry: Mapping[str, Any], *keys: str, dimension: str) -> None:
    missing = sorted(k for k in keys if not entry.get(k))
    if missing:
        raise ValueError(
            f"entrada de `{dimension}` sem os campos que o planner usa: "
            f"{', '.join(missing)} em {entry!r}"
        )


def _links(raw: Any) -> tuple[DesiredLink, ...] | None:
    if raw is None:
        return None
    out: list[DesiredLink] = []
    for entry in _entries(raw):
        _require(entry, "name", "target", "why", dimension="links")
        out.append(
            DesiredLink(name=entry["name"], target=expand(entry["target"]), why=entry["why"])
        )
    return tuple(out)


def _retire(raw: Any) -> tuple[DesiredRetire, ...] | None:
    if raw is None:
        return None
    out: list[DesiredRetire] = []
    for entry in _entries(raw):
        _require(entry, "path", "why", dimension="retire")
        out.append(DesiredRetire(path=expand(entry["path"]), why=entry["why"]))
    return tuple(out)


def _secrets(raw: Any) -> tuple[DesiredSecret, ...] | None:
    if raw is None:
        return None
    out: list[DesiredSecret] = []
    for entry in _entries(raw):
        _require(entry, "path", "why", dimension="read_denylist")
        out.append(DesiredSecret(path=expand(entry["path"]), why=entry["why"]))
    return tuple(out)


def _skills(raw: Any) -> DesiredSkills | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("`skills` desejado precisa ser um objeto")
    return DesiredSkills(
        promote=_moves(raw.get("promote") or (), dimension="skills.promote"),
        discard=_moves(raw.get("discard") or (), dimension="skills.discard"),
    )


def _moves(raw: Any, *, dimension: str) -> tuple[SkillMove, ...]:
    out: list[SkillMove] = []
    for entry in _entries(raw):
        _require(entry, "name", "source", "why", dimension=dimension)
        out.append(
            SkillMove(
                name=entry["name"],
                source=entry["source"],
                why=entry["why"],
                superseded_by=entry.get("superseded_by", ""),
            )
        )
    return tuple(out)


def _entries(raw: Any) -> Sequence[Mapping[str, Any]]:
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        raise ValueError(f"esperava uma lista de entradas, veio {type(raw).__name__}")
    entries: list[Mapping[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise ValueError(f"entrada de configuração precisa ser um objeto: {entry!r}")
        entries.append(entry)
    return entries


def load_desired(path: Path = DEFAULT_CONFIG_PATH) -> Desired:
    return Desired.from_dict(json.loads(path.read_text(encoding="utf-8")))
