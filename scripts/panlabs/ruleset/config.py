"""A configuracao desejada: dado versionado, carregado de arquivo.

Os valores sao decididos pela spec de Org #2 e vivem em `config/ruleset.json`.
Este modulo entrega o esqueleto do dado e a sua leitura -- nunca os valores.

Uma chave ausente ou nula significa **ainda nao decidido**, e o planner nao
planeja nada para a dimensao correspondente. Isso e diferente de "decidido como
vazio": `retire_classic_protection: false` e uma decisao, `null` nao e.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["DEFAULT_CONFIG_PATH", "Desired", "load_desired"]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "ruleset.json"

KNOWN_KEYS = ("ruleset", "retire_classic_protection")
REQUIRED_RULESET_KEYS = ("name", "target", "enforcement", "bypass_actors", "conditions", "rules")


@dataclass(frozen=True)
class Desired:
    """O estado desejado da protecao de branch, para todo repo da org."""

    ruleset: Mapping[str, Any] | None = None
    retire_classic_protection: bool | None = None

    @property
    def undecided(self) -> tuple[str, ...]:
        """As dimensoes que ainda esperam decisao da spec de Org #2."""
        pending = [key for key in KNOWN_KEYS if getattr(self, key) is None]
        return tuple(sorted(pending))

    @property
    def is_decided(self) -> bool:
        return not self.undecided

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Desired:
        unknown = sorted(k for k in raw if not k.startswith("_") and k not in KNOWN_KEYS)
        if unknown:
            raise ValueError(
                f"chave desconhecida na configuracao desejada: {', '.join(unknown)}; "
                f"chaves validas: {', '.join(KNOWN_KEYS)}"
            )

        ruleset = raw.get("ruleset")
        if ruleset is not None:
            missing = sorted(k for k in REQUIRED_RULESET_KEYS if k not in ruleset)
            if missing:
                raise ValueError(
                    f"ruleset desejado sem os campos que o planner compara: {', '.join(missing)}"
                )

        return cls(ruleset=ruleset, retire_classic_protection=raw.get("retire_classic_protection"))


def load_desired(path: Path = DEFAULT_CONFIG_PATH) -> Desired:
    return Desired.from_dict(json.loads(path.read_text(encoding="utf-8")))
