"""O punhado de valores que a anatomia cobra e que são decisão, não catálogo.

O catálogo de itens é código, porque um item é um predicado. Mas três dimensões
existem como item e ainda esperam o **valor** com que comparar: a licença
uniforme e os dois majors de runtime para os quais a frota converge. Elas vivem
em `config/anatomy.json`, e `null` ali significa **ainda não decidido** -- o item
não é avaliado, o que é diferente de decidido-como-vazio e diferente de conforme.

Uma quarta dimensão não mora aqui e sim em `config/org.json`: a exceção de wiki.
Ela é decisão da spec de Org #2, e o checker a **lê** em vez de cravar, pelo mesmo
loader que o script de org usa. Duplicá-la seria criar duas listas de exceção que
divergem no dia em que uma for editada, e o repo que a exceção protege apareceria
como deriva sem que ninguém tivesse mudado de ideia.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from panlabs.org.config import DEFAULT_CONFIG_PATH as DEFAULT_ORG_CONFIG_PATH
from panlabs.org.config import load_desired as load_org_desired

__all__ = ["DEFAULT_ANATOMY_PATH", "Desired", "load_desired"]

DEFAULT_ANATOMY_PATH = Path(__file__).resolve().parents[3] / "config" / "anatomy.json"

KNOWN_KEYS = ("license", "python_series", "node_series")


@dataclass(frozen=True)
class Desired:
    """Os valores contra os quais alguns itens comparam. `None` é não decidido."""

    license: str | None = None
    python_series: str | None = None
    node_series: str | None = None
    wiki: bool | None = None
    wiki_exceptions: frozenset[str] = frozenset()

    @property
    def undecided(self) -> tuple[str, ...]:
        """As dimensões que ainda esperam decisão, e cujos itens não são avaliados."""
        return tuple(sorted(key for key in KNOWN_KEYS if getattr(self, key) is None))


def load_desired(
    anatomy_path: Path = DEFAULT_ANATOMY_PATH,
    org_path: Path = DEFAULT_ORG_CONFIG_PATH,
) -> Desired:
    raw: dict[str, Any] = json.loads(anatomy_path.read_text(encoding="utf-8"))

    unknown = sorted(k for k in raw if not k.startswith("_") and k not in KNOWN_KEYS)
    if unknown:
        raise ValueError(
            f"chave desconhecida em {anatomy_path}: {', '.join(unknown)}; "
            f"chaves válidas: {', '.join(KNOWN_KEYS)}"
        )

    org = load_org_desired(org_path)
    wiki = org.wiki
    return Desired(
        license=raw.get("license"),
        python_series=raw.get("python_series"),
        node_series=raw.get("node_series"),
        wiki=None if wiki is None else bool(wiki.get("enabled")),
        wiki_exceptions=org.wiki_exceptions(),
    )
