"""O tipo de cada repositório: dado versionado, não inferido.

Tipos são nomeados e finitos (`ANATOMY.md`); classificar um repositório é
escolha do operador quando ele nasce, não um cálculo do checker. Um
repositório ausente deste mapa, ou com valor `null`, ainda não foi
classificado: os itens de escopo tipo não o alcançam, e isso não é deriva.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["DEFAULT_REPO_TYPES_PATH", "load_repo_types"]

DEFAULT_REPO_TYPES_PATH = Path(__file__).resolve().parents[3] / "config" / "repo-types.json"


def load_repo_types(path: Path = DEFAULT_REPO_TYPES_PATH) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        key: value
        for key, value in raw.items()
        if not key.startswith("_") and isinstance(value, str)
    }
