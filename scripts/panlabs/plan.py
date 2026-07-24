"""O seam: o vocabulário de plano compartilhado por todo script deste repo.

Este é o ponto mais alto disponível: acima dele só existe a chamada real de API;
abaixo dele começa detalhe de implementação. E é **um só** — o mesmo formato
serve ao ruleset, ao checker, ao reconcile de workspaces e à poda do heartbeat.

    plan(observed, desired) -> Plan   # puro, testado com fixtures
    apply(Plan, efeitos)             # fino, sem teste

`Plan` é uma sequência de `PlanItem`, e cada item carrega **ação, alvo e motivo**.
O motivo é obrigatório por construção: um plano que diz "vai aplicar proteção em X"
sem dizer o que está divergente não é revisável, e portanto não é um plano válido.

O `payload` de um item é o dado que o efeito precisa para agir — tipicamente o
corpo exato de uma chamada de API. Ele existe para que o applier não precise
decidir nada: o planner já calculou o que enviar.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Effect", "Plan", "PlanItem", "apply"]


@dataclass(frozen=True)
class PlanItem:
    """Uma ação pendente sobre um alvo, com o motivo que a justifica."""

    action: str
    target: str
    reason: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action:
            raise ValueError("item de plano sem ação")
        if not self.target:
            raise ValueError("item de plano sem alvo")
        if not self.reason:
            raise ValueError(f"item de plano sem motivo: {self.action} em {self.target}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "target": self.target,
            "reason": self.reason,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class Plan:
    """A saída pura de um planner, antes de qualquer efeito.

    Serializável e legível: é o que o teste compara e o que o operador lê antes
    de aprovar. A ordem dos itens é a ordem em que o planner os produziu, e é
    determinística — plano instável não é comparável nem revisável.
    """

    items: tuple[PlanItem, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[PlanItem]:
        return iter(self.items)

    def to_dict(self) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in self.items]}

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=True)

    def render(self) -> str:
        """Renderiza o plano para leitura humana, agrupado por alvo.

        Um plano vazio não afirma convergência: quem sabe *por que* ele saiu vazio
        é quem chamou o planner, não o plano. Dizer "já está tudo certo" quando na
        verdade nada foi decidido seria a única leitura errada possível aqui.
        """
        if not self.items:
            return "Nada a fazer: nenhum item de plano."

        by_target: dict[str, list[PlanItem]] = {}
        for item in self.items:
            by_target.setdefault(item.target, []).append(item)

        width = max(len(item.action) for item in self.items)
        lines: list[str] = []
        for target, items in by_target.items():
            lines.append(target)
            for item in items:
                lines.append(f"  {item.action.ljust(width)}  {item.reason}")
            lines.append("")

        plural = "itens" if len(self.items) > 1 else "item"
        lines.append(f"{len(self.items)} {plural} em {len(by_target)} alvo(s).")
        return "\n".join(lines)


Effect = Callable[[PlanItem], None]
"""O efeito que realiza um item de plano. Não decide nada — só age."""


def apply(plan: Plan, effects: Mapping[str, Effect]) -> None:
    """Realiza cada item do plano pelo efeito registrado para a sua ação.

    Não há ramificação de decisão aqui, e não pode haver: `effects` é uma tabela
    de despacho, e a escolha de qual ação cabe a cada alvo já foi feita pelo
    planner. Uma ação sem efeito registrado é erro de programação, não um caso a
    tratar — por isso a busca falha em vez de ser ignorada.
    """
    for item in plan:
        effects[item.action](item)
