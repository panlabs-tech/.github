"""A configuração desejada do espaço de trabalho: dado versionado, lido de arquivo.

Os valores são decididos pela spec de Máquina #3 e vivem em `config/workspace.json`.
Este módulo entrega o esqueleto do dado e a sua leitura, nunca os valores.

Uma chave ausente ou nula significa **ainda não decidido**, e o planner não planeja
nada para a dimensão correspondente. Isso é diferente de "decidido como vazio":
`migrated_from: []` afirma que nenhuma conta antiga precisa de reescrita, `null` não
afirma nada.

O que **não** mora aqui é lista de repo nenhuma: o alvo vem sempre da org viva.
O dado descreve endereço e forma, e o critério de descarte é decisão do planner,
não configuração: um critério que se desliga por arquivo não é critério.
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
    "expand",
    "load_desired",
]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "workspace.json"

KNOWN_KEYS = ("root", "remote", "migrated_from", "worktrees")


def expand(path: str) -> str:
    """`~/x` vira o caminho absoluto desta máquina, sem resolver link nenhum.

    Igual ao script de máquina, e pelo mesmo motivo: o dado é o mesmo em qualquer
    máquina, e a expansão é local. Resolver link aqui seria pior do que inútil,
    porque o vínculo de um worktree com o pai é caminho absoluto **como escrito**.
    """
    return str(Path(path).expanduser())


@dataclass(frozen=True)
class Desired:
    """O estado estacionário declarado do espaço de trabalho."""

    root: str | None = None
    remote: str | None = None
    migrated_from: tuple[str, ...] | None = None
    worktrees: str | None = None

    @property
    def undecided(self) -> tuple[str, ...]:
        """As dimensões que ainda esperam decisão da spec de Máquina #3."""
        return tuple(sorted(key for key in KNOWN_KEYS if getattr(self, key) is None))

    @property
    def is_decided(self) -> bool:
        return not self.undecided

    def url_for(self, org: str, name: str) -> str:
        """O remote canônico de um repo da org, montado a partir do dado.

        Formatar um endereço não é decidir nada: o formato é versionado, e é ele
        que faz o planner não cravar um host em código.
        """
        if self.remote is None:
            return ""
        return self.remote.format(org=org, name=name)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Desired:
        unknown = sorted(k for k in raw if not k.startswith("_") and k not in KNOWN_KEYS)
        if unknown:
            raise ValueError(
                f"chave desconhecida na configuração desejada: {', '.join(unknown)}; "
                f"chaves válidas: {', '.join(KNOWN_KEYS)}"
            )

        return cls(
            root=_maybe_expand(raw.get("root")),
            remote=_remote(raw.get("remote")),
            migrated_from=_owners(raw.get("migrated_from")),
            worktrees=_relative(raw.get("worktrees")),
        )


def _maybe_expand(value: Any) -> str | None:
    return None if value is None else expand(str(value))


def _remote(raw: Any) -> str | None:
    """O molde do remote canônico, checado nos dois campos que o planner preenche."""
    if raw is None:
        return None
    template = str(raw)
    missing = sorted(field for field in ("{org}", "{name}") if field not in template)
    if missing:
        raise ValueError(
            f"`remote` desejado não tem {', '.join(missing)}: um molde sem os dois campos "
            f"produziria o mesmo endereço para toda a org ({template!r})"
        )
    return template


def _owners(raw: Any) -> tuple[str, ...] | None:
    if raw is None:
        return None
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        raise ValueError(f"`migrated_from` esperava uma lista de donos, veio {type(raw).__name__}")
    return tuple(str(owner) for owner in raw)


def _relative(raw: Any) -> str | None:
    """Onde um worktree nasce dentro do pai, sempre relativo a ele.

    Absoluto aqui produziria worktrees de repos diferentes no mesmo lugar, que é
    exatamente o layout solto que esta issue desfaz.
    """
    if raw is None:
        return None
    path = str(raw).strip("/")
    if not path:
        raise ValueError("`worktrees` desejado vazio: um worktree precisa nascer em algum lugar")
    if str(raw).startswith("/") or str(raw).startswith("~"):
        raise ValueError(
            f"`worktrees` desejado precisa ser relativo ao repositório pai, veio {raw!r}"
        )
    return path


def load_desired(path: Path = DEFAULT_CONFIG_PATH) -> Desired:
    return Desired.from_dict(json.loads(path.read_text(encoding="utf-8")))
