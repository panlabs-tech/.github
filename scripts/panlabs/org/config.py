"""A configuração desejada de org e repo: dado versionado, carregado de arquivo.

Os valores são decididos pela spec de Org #2 e vivem em `config/org.json`. Este
módulo entrega o esqueleto do dado e a sua leitura, nunca os valores.

Uma chave ausente ou nula significa **ainda não decidido**, e o planner não
planeja nada para a dimensão correspondente. Isso é diferente de "decidido como
vazio": `wiki.enabled: false` é uma decisão, `wiki: null` não é.

A exceção de wiki mora *dentro* da dimensão que ela excepciona, e é obrigatória
quando a dimensão é decidida. Uma exceção que se pode esquecer de escrever é uma
exceção que um dia vira `if` escondido no planner, que é exatamente o que este
formato existe para impedir.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["DEFAULT_CONFIG_PATH", "Desired", "load_desired"]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "org.json"

KNOWN_KEYS = (
    "actions_can_approve_pull_requests",
    "two_factor_requirement",
    "new_repo_security_defaults",
    "org_description",
    "pinned_repos",
    "secret_scanning",
    "push_protection",
    "dependabot_alerts",
    "dependabot_security_updates",
    "repo_descriptions",
    "repo_topics",
    "wiki",
)

REQUIRED_WIKI_KEYS = ("enabled", "exceptions")


@dataclass(frozen=True)
class Desired:
    """O estado desejado da org e dos seus repos, dimensão por dimensão."""

    actions_can_approve_pull_requests: bool | None = None
    two_factor_requirement: bool | None = None
    new_repo_security_defaults: Mapping[str, bool] | None = None
    org_description: str | None = None
    pinned_repos: Sequence[str] | None = None
    secret_scanning: bool | None = None
    push_protection: bool | None = None
    dependabot_alerts: bool | None = None
    dependabot_security_updates: bool | None = None
    repo_descriptions: Mapping[str, str] | None = None
    repo_topics: Mapping[str, Sequence[str]] | None = None
    wiki: Mapping[str, Any] | None = None

    @property
    def undecided(self) -> tuple[str, ...]:
        """As dimensões que ainda esperam decisão."""
        pending = [key for key in KNOWN_KEYS if getattr(self, key) is None]
        return tuple(sorted(pending))

    @property
    def is_decided(self) -> bool:
        return not self.undecided

    def wiki_exceptions(self) -> frozenset[str]:
        """Os repos que esta configuração declara fora da dimensão wiki."""
        if self.wiki is None:
            return frozenset()
        return frozenset(self.wiki.get("exceptions") or ())

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Desired:
        unknown = sorted(k for k in raw if not k.startswith("_") and k not in KNOWN_KEYS)
        if unknown:
            raise ValueError(
                f"chave desconhecida na configuração desejada: {', '.join(unknown)}; "
                f"chaves válidas: {', '.join(KNOWN_KEYS)}"
            )

        wiki = raw.get("wiki")
        if wiki is not None:
            missing = sorted(k for k in REQUIRED_WIKI_KEYS if k not in wiki)
            if missing:
                raise ValueError(
                    f"dimensão wiki sem os campos que o planner precisa: {', '.join(missing)}; "
                    "a lista de exceções é obrigatória mesmo vazia, para que esquecê-la "
                    "não desligue um wiki gerado por automação"
                )

        return cls(**{key: raw.get(key) for key in KNOWN_KEYS})


def load_desired(path: Path = DEFAULT_CONFIG_PATH) -> Desired:
    return Desired.from_dict(json.loads(path.read_text(encoding="utf-8")))
