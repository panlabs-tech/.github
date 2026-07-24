"""O seam: o vocabulario de plano compartilhado por todo script deste repo.

Este e o ponto mais alto disponivel: acima dele so existe a chamada real de API;
abaixo dele comeca detalhe de implementacao. E e **um so** -- o mesmo formato
serve ao ruleset, ao checker, ao reconcile de workspaces e a poda do heartbeat.

    plan(observed) -> Plan        # puro, testado com fixtures
    apply(Plan)    -> efeitos     # fino, sem teste

`Plan` e uma sequencia de `PlanItem`, e cada item carrega **acao, alvo e motivo**.
O motivo e obrigatorio por construcao: um plano que diz "vai aplicar protecao em X"
sem dizer o que esta divergente nao e revisavel, e portanto nao e um plano valido.

O `payload` de um item e o dado que o efeito precisa para agir -- tipicamente o
corpo exato de uma chamada de API. Ele existe para que o applier nao precise
decidir nada: o planner ja calculou o que enviar.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Effect", "Plan", "PlanItem", "apply"]


@dataclass(frozen=True)
class PlanItem:
    """Uma acao pendente sobre um alvo, com o motivo que a justifica."""

    action: str
    target: str
    reason: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action:
            raise ValueError("item de plano sem acao")
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

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> PlanItem:
        return cls(
            action=raw["action"],
            target=raw["target"],
            reason=raw["reason"],
            payload=raw.get("payload") or {},
        )


@dataclass(frozen=True)
class Plan:
    """A saida pura de um planner, antes de qualquer efeito.

    Serializavel e legivel: e o que o teste compara e o que o operador le antes
    de aprovar. A ordem dos itens e a ordem em que o planner os produziu, e e
    deterministica -- plano instavel nao e comparavel nem revisavel.
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

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Plan:
        return cls(tuple(PlanItem.from_dict(item) for item in raw.get("items", ())))

    def render(self) -> str:
        """Renderiza o plano para leitura humana, agrupado por alvo.

        Um plano vazio nao afirma convergencia: quem sabe *por que* ele saiu vazio
        e quem chamou o planner, nao o plano. Dizer "ja esta tudo certo" quando na
        verdade nada foi decidido seria a unica leitura errada possivel aqui.
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
"""O efeito que realiza um item de plano. Nao decide nada -- so age."""


def apply(plan: Plan, effects: Mapping[str, Effect]) -> None:
    """Realiza cada item do plano pelo efeito registrado para a sua acao.

    Nao ha ramificacao de decisao aqui, e nao pode haver: `effects` e uma tabela
    de despacho, e a escolha de qual acao cabe a cada alvo ja foi feita pelo
    planner. Uma acao sem efeito registrado e um erro de programacao, nao um caso
    a tratar -- por isso a busca falha em vez de ser ignorada.
    """
    for item in plan:
        effects[item.action](item)
