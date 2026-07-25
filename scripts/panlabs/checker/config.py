"""O dado que a observação do checker lê: dois arquivos, com naturezas diferentes.

`repo-types.json` é **classificação**: tipos são nomeados e finitos (`ANATOMY.md`),
e classificar um repositório é escolha do operador quando ele nasce, não um
cálculo do checker. Um repositório ausente do mapa, ou com valor `null`, ainda não
foi classificado: os itens de escopo tipo não o alcançam, e isso não é deriva.

`checker.json` é **parâmetro de leitura**: o conjunto de arquivos cujo conteúdo é
observado. Ele é declarado porque a alternativa é varredura cega, e porque o custo
por repositório precisa caber numa consulta só. Aqui, ao contrário de um planner,
não decidido e decidido-como-vazio têm o mesmo efeito -- nada é lido --, porque
observação não planeja nada; a distinção que importa vive nos planners.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_CHECKER_CONFIG_PATH",
    "DEFAULT_REPO_TYPES_PATH",
    "VALID_TYPES",
    "load_read_files",
    "load_repo_types",
]

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"

DEFAULT_REPO_TYPES_PATH = CONFIG_DIR / "repo-types.json"
DEFAULT_CHECKER_CONFIG_PATH = CONFIG_DIR / "checker.json"

VALID_TYPES = frozenset({"aplicacao", "modulo-infraestrutura", "skills", "meta", "dotfiles"})
"""Os cinco tipos nomeados e finitos de `ANATOMY.md`. Nenhum sexto tipo existe."""

KNOWN_KEYS = ("read_files",)


def load_repo_types(path: Path = DEFAULT_REPO_TYPES_PATH) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    types = {
        key: value
        for key, value in raw.items()
        if not key.startswith("_") and isinstance(value, str)
    }

    unknown = sorted(set(types.values()) - VALID_TYPES)
    if unknown:
        raise ValueError(
            f"tipo desconhecido em {path}: {', '.join(unknown)}; "
            f"os cinco tipos válidos (ANATOMY.md) são {', '.join(sorted(VALID_TYPES))}"
        )

    return types


def load_read_files(path: Path = DEFAULT_CHECKER_CONFIG_PATH) -> tuple[str, ...]:
    """Os arquivos cujo conteúdo é lido, na ordem declarada.

    A ordem é preservada porque ela é a ordem dos apelidos da consulta, e um
    conjunto lido em ordem instável produziria retratos que diferem sem que nada
    tenha mudado no repositório -- e o retrato é fixture comparável.
    """
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    unknown = sorted(k for k in raw if not k.startswith("_") and k not in KNOWN_KEYS)
    if unknown:
        raise ValueError(
            f"chave desconhecida em {path}: {', '.join(unknown)}; "
            f"chaves válidas: {', '.join(KNOWN_KEYS)}"
        )

    declared = raw.get("read_files")
    if declared is None:
        return ()
    return _paths(declared, path)


def _paths(declared: Any, source: Path) -> tuple[str, ...]:
    if not isinstance(declared, Sequence) or isinstance(declared, str):
        raise ValueError(f"`read_files` em {source} precisa ser uma lista de caminhos")

    paths = [str(entry) for entry in declared]
    repeated = sorted({path for path in paths if paths.count(path) > 1})
    if repeated:
        raise ValueError(
            f"caminho repetido em `read_files` de {source}: {', '.join(repeated)}; "
            "cada arquivo já é lido uma vez por repositório, e repeti-lo só pagaria duas vezes "
            "pela mesma resposta"
        )
    return tuple(paths)
