"""O seam: o vocabulário de plano compartilhado por todo script deste repo.

Este é o ponto mais alto disponível: acima dele só existe a chamada real de API;
abaixo dele começa detalhe de implementação. E é **um só**: o mesmo formato
serve ao ruleset, ao checker, ao reconcile de workspaces e à poda do heartbeat.

    plan(observed, desired) -> Plan   # puro, testado com fixtures
    apply(Plan, efeitos)             # fino, sem teste

`Plan` é uma sequência de `PlanItem`, e cada item carrega **ação, alvo e motivo**.
O motivo é obrigatório por construção: um plano que diz "vai aplicar proteção em X"
sem dizer o que está divergente não é revisável, e portanto não é um plano válido.

O `payload` de um item é o dado que o efeito precisa para agir, tipicamente o
corpo exato de uma chamada de API. Ele existe para que o applier não precise
decidir nada: o planner já calculou o que enviar.

O `hold` de um item é o oposto do payload: o motivo pelo qual ele **não** vai ser
realizado agora. Um item retido continua no plano, para ser lido, e o `apply` não
o executa. Isso existe porque "some do plano" e "não é seguro aplicar hoje" são
coisas diferentes, e esconder a segunda faria o plano mentir sobre a deriva.

O seam carrega **duas palavras para ausência**, e elas levam a lugares opostos.
"Não decidido" é ausência no dado versionado, e nada é planejado para ela
(`report_undecided`). `Unobservable` é ausência na plataforma, e ela é planejada
e **retida**: a dimensão existe, o operador a quer, e ninguém conseguiu medi-la.
Um nome só para as duas faria o plano vazio significar duas coisas incompatíveis.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "Effect",
    "Plan",
    "PlanItem",
    "Unobservable",
    "apply",
    "dump_raw",
    "load_raw",
    "report_held",
    "report_undecided",
    "why_empty",
]


@dataclass(frozen=True)
class Unobservable:
    """Uma dimensão que a plataforma não mostrou, com o que ela disse a respeito.

    É o terceiro valor entre "observado ligado" e "observado desligado", e existe
    porque os dois primeiros são afirmações sobre o alvo que ninguém pode fazer
    aqui. Um repositório privado num plano que não oferece rulesets não tem
    ruleset desligado: ele tem ruleset que este observador não alcança, e a
    diferença decide se o plano cobra convergência ou explica por que não pode.

    **É um tipo, e não `None` nem uma flag ao lado, de propósito.** `bool | None`
    faria os três estados caberem no mesmo `if not`, e o primeiro leitor distraído
    transformaria "não consegui ler" em "está desligado", que é exatamente a
    mentira que este repo proíbe em `org/observe.py` e em `ANATOMY.md`. Sendo tipo,
    quem ler a dimensão é obrigado pelo verificador de tipos a decidir o que fazer
    com o terceiro caso.

    O motivo é obrigatório por construção, pela mesma razão que o de `PlanItem`:
    ele vira o `hold` do item retido, e retenção sem motivo escrito não é revisável.
    Onde a plataforma se explicou, ele **cita o que ela disse**, em vez de traduzir:
    um 403 de plano e um 403 de permissão só se distinguem por esse texto, e
    parafrasear seria escolher qual dos dois aconteceu sem ter como saber.
    """

    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("dimensão não observável sem motivo escrito")


@dataclass(frozen=True)
class PlanItem:
    """Uma ação pendente sobre um alvo, com o motivo que a justifica.

    Com `hold` preenchido, a ação está planejada e **retida**: o plano a mostra,
    o `apply` não a realiza, e o texto do `hold` diz por quê. Reter é decisão do
    planner como qualquer outra, e por isso vem com motivo escrito, igual à ação.
    """

    action: str
    target: str
    reason: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    hold: str = ""

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
            "hold": self.hold,
        }


@dataclass(frozen=True)
class Plan:
    """A saída pura de um planner, antes de qualquer efeito.

    Serializável e legível: é o que o teste compara e o que o operador lê antes
    de aprovar. A ordem dos itens é a ordem em que o planner os produziu, e é
    determinística: plano instável não é comparável nem revisável.
    """

    items: tuple[PlanItem, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[PlanItem]:
        return iter(self.items)

    @property
    def applicable(self) -> tuple[PlanItem, ...]:
        """Os itens que o `apply` realiza: tudo que não está retido."""
        return tuple(item for item in self.items if not item.hold)

    @property
    def held(self) -> tuple[PlanItem, ...]:
        """Os itens retidos: planejados, mostrados, e deliberadamente não aplicados."""
        return tuple(item for item in self.items if item.hold)

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
        mark = "retido " if self.held else ""
        blank = " " * len(mark)
        lines: list[str] = []
        for target, items in by_target.items():
            lines.append(target)
            for item in items:
                prefix = mark if item.hold else blank
                lines.append(f"  {prefix}{item.action.ljust(width)}  {item.reason}")
            for why in sorted({item.hold for item in items if item.hold}):
                lines.append(f"  retido porque {why}")
            lines.append("")

        plural = "itens" if len(self.items) > 1 else "item"
        lines.append(f"{len(self.items)} {plural} em {len(by_target)} alvo(s).")
        if self.held:
            lines.append(f"{len(self.held)} retido(s): planejado(s) e não aplicado(s).")
        return "\n".join(lines)


def load_raw(observed_path: Path | None, fetch: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Lê o retrato cru de um arquivo salvo, ou busca da fonte viva.

    Comum a todo CLI deste repo: ler um retrato salvo nunca deve tocar a fonte
    viva, e as duas metades (arquivo ou busca) devolvem o mesmo formato cru,
    antes de qualquer `build_observed` interpretá-lo.
    """
    if observed_path is not None:
        return json.loads(observed_path.read_text(encoding="utf-8"))
    return fetch()


def dump_raw(path: Path | None, raw: Mapping[str, Any]) -> None:
    """Grava o retrato cru observado, para virar fixture. Sem `path`, não faz nada."""
    if path is None:
        return
    path.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )


def report_undecided(undecided: Sequence[str], config: Path) -> None:
    """Avisa quais dimensões do dado ainda não foram decididas. Sem nenhuma, cala.

    Mora aqui, e não em cada CLI, porque "não decidido" é vocabulário do seam:
    todo script deste repo carrega dado versionado onde `null` significa a mesma
    coisa, e dois textos diferentes para o mesmo fato divergiriam com o tempo.
    """
    if not undecided:
        return
    print(
        f"Configuração desejada incompleta em {config}: "
        f"{', '.join(undecided)} ainda sem decisão.\n"
        "Nada é planejado para uma dimensão não decidida. Os valores são da spec de Org #2.\n",
        file=sys.stderr,
    )


def report_held(plan: Plan) -> None:
    """Devolve ao operador cada item retido, com o motivo que o planner escreveu.

    Mora aqui, e não em cada CLI, pelo mesmo motivo de `report_undecided`: `hold`
    é vocabulário do seam. Três CLIs escreviam este bloco igual e o quarto
    escrevia uma frase própria, que nomeava **uma** causa de retenção; no dia em
    que aquele script ganhou uma segunda causa, a frase passou a mandar o operador
    esperar pela coisa errada. Um relato só, alimentado pelo motivo de cada item,
    não tem como envelhecer assim: quem sabe por que o item foi retido é o planner
    que o reteve, e o motivo já viaja escrito dentro dele.

    Sai no `stderr` porque não é o plano: é o recado de quem digitou `--apply` e
    vai ver menos coisa aplicada do que o plano mostrou. Quando não sobra nada
    aplicável, dizê-lo é parte do recado: silêncio depois de `--apply` se lê como
    aplicação bem-sucedida, e aqui não houve aplicação nenhuma.
    """
    if not plan.held:
        return
    print(
        f"\n{len(plan.held)} item(ns) do plano estão retidos e continuam com você:",
        file=sys.stderr,
    )
    for item in plan.held:
        print(f"  {item.action}  {item.target}: {item.hold}", file=sys.stderr)
    if not plan.applicable:
        print("Nada a aplicar: todo o plano está retido.", file=sys.stderr)


def why_empty(plan: Plan, undecided: Sequence[str], config: Path, *, subject: str) -> str:
    """Um plano vazio tem duas causas opostas, e confundi-las seria caro.

    Se a configuração desejada ainda não foi decidida, vazio significa "nada foi
    pedido": não "está tudo conforme". Só quem carregou o dado sabe a diferença,
    e por isso o `undecided` entra como argumento em vez de ser adivinhado aqui.
    """
    if plan:
        return ""
    if not undecided:
        return "O estado observado já converge com o desejado."
    return (
        f"Isso NÃO quer dizer que {subject} está conforme: {', '.join(undecided)} "
        f"ainda não foi decidido em {config}, então nada foi pedido."
    )


Effect = Callable[[PlanItem], None]
"""O efeito que realiza um item de plano. Não decide nada, só age."""


def apply(plan: Plan, effects: Mapping[str, Effect]) -> None:
    """Realiza cada item do plano pelo efeito registrado para a sua ação.

    Não há ramificação de decisão aqui, e não pode haver: `effects` é uma tabela
    de despacho, e a escolha de qual ação cabe a cada alvo já foi feita pelo
    planner. Uma ação sem efeito registrado é erro de programação, não um caso a
    tratar: por isso a busca falha em vez de ser ignorada.

    Item retido também não é decisão daqui: o planner já decidiu retê-lo e
    escreveu o motivo no item. Ao `apply` resta não agir.
    """
    for item in plan.applicable:
        effects[item.action](item)
