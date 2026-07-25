"""A configuração desejada: dado versionado, carregado de arquivo.

Os valores são decididos pela spec de Org #2 e vivem em `config/ruleset.json`.
Este módulo entrega o esqueleto do dado e a sua leitura, nunca os valores.

Uma chave ausente ou nula significa **ainda não decidido**, e o planner não
planeja nada para a dimensão correspondente. Isso é diferente de "decidido como
vazio": `retire_classic_protection: false` é uma decisão, `null` não é.

O ruleset e a configuração do repositório são dimensões separadas no dado porque
são recursos separados na API, mas uma delas não faz sentido sem a outra: exigir
assinatura de commit sem restringir o merge a squash reprovaria o commit local do
agente, que não é assinado. As duas moram no mesmo arquivo por isso.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from panlabs.ruleset.model import REPO_SETTINGS_KEYS

__all__ = ["DEFAULT_CONFIG_PATH", "Desired", "load_desired"]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "ruleset.json"

KNOWN_KEYS = ("ruleset", "repo_settings", "retire_classic_protection")
REQUIRED_RULESET_KEYS = ("name", "target", "enforcement", "bypass_actors", "conditions", "rules")
REQUIRED_STATUS_CHECKS_RULE = "required_status_checks"


@dataclass(frozen=True)
class Desired:
    """O estado desejado da proteção de branch, para todo repo da org."""

    ruleset: Mapping[str, Any] | None = None
    repo_settings: Mapping[str, Any] | None = None
    retire_classic_protection: bool | None = None

    @property
    def undecided(self) -> tuple[str, ...]:
        """As dimensões que ainda esperam decisão da spec de Org #2."""
        pending = [key for key in KNOWN_KEYS if getattr(self, key) is None]
        return tuple(sorted(pending))

    @property
    def is_decided(self) -> bool:
        return not self.undecided

    @property
    def required_check_contexts(self) -> tuple[str, ...]:
        """Os nomes de check que o ruleset desejado exige, lidos do próprio dado.

        O contrato de nomes é dado, não código: quem decide quais checks são
        exigidos é `config/ruleset.json`, e é dele que sai o critério usado para
        saber se um repo pode receber esse contrato hoje sem pendurar o merge.
        """
        if self.ruleset is None:
            return ()
        for rule in self.ruleset.get("rules") or ():
            if rule.get("type") != REQUIRED_STATUS_CHECKS_RULE:
                continue
            checks = (rule.get("parameters") or {}).get(REQUIRED_STATUS_CHECKS_RULE) or ()
            return tuple(sorted(check["context"] for check in checks if "context" in check))
        return ()

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Desired:
        unknown = sorted(k for k in raw if not k.startswith("_") and k not in KNOWN_KEYS)
        if unknown:
            raise ValueError(
                f"chave desconhecida na configuração desejada: {', '.join(unknown)}; "
                f"chaves válidas: {', '.join(KNOWN_KEYS)}"
            )

        ruleset = raw.get("ruleset")
        if ruleset is not None:
            missing = sorted(k for k in REQUIRED_RULESET_KEYS if k not in ruleset)
            if missing:
                raise ValueError(
                    f"ruleset desejado sem os campos que o planner compara: {', '.join(missing)}"
                )

        settings = raw.get("repo_settings")
        if settings is not None:
            # A API ignora em silêncio um campo que não conhece, e o plano ficaria
            # eternamente divergente sem que ninguém entendesse por quê.
            unknown_settings = sorted(k for k in settings if k not in REPO_SETTINGS_KEYS)
            if unknown_settings:
                raise ValueError(
                    "configuração de repositório desconhecida: "
                    f"{', '.join(unknown_settings)}; chaves válidas: "
                    f"{', '.join(REPO_SETTINGS_KEYS)}"
                )

        return cls(
            ruleset=ruleset,
            repo_settings=settings,
            retire_classic_protection=raw.get("retire_classic_protection"),
        )


def load_desired(path: Path = DEFAULT_CONFIG_PATH) -> Desired:
    return Desired.from_dict(json.loads(path.read_text(encoding="utf-8")))
