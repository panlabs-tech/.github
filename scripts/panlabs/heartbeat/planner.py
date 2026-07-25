"""Onde toda decisão do heartbeat mora. Puro, testado.

O heartbeat é um **hospedeiro de passos**, e não um script monolítico. Um passo
declara três coisas, todas como dado: em qual ramo roda, qual é a cadência dele e
qual canal de alarme ele usa. Este módulo não conhece passo nenhum pelo nome.

Quatro decisões vivem aqui:

- **O ramo é do estado observado.** Poda exige o WSL de pé, compactação exige o
  WSL parado, e a tarefa nunca liga nem desliga nada: ela faz o que for seguro
  agora. Um estado **não consultado** não é "parado", e confundir os dois rodaria
  a compactação contra um disco vivo.
- **Disparo diário não é cadência da ação.** O disparo diário existe para dar
  cerca de trinta chances por mês de encontrar o WSL no estado certo, não porque a
  ação precise ser diária. Um passo cujo prazo não venceu não entra no plano.
- **O alarme vem antes da ação.** Notificar primeiro é o que impede um passo que
  trava de engolir o alarme de disco, que é o único vigia de uma métrica que não
  se enxerga de dentro do WSL.
- **Versão velha de browser é o desperdício; browser não é.** Manter a revisão
  mais nova de cada família custa quase nada e não quebra o próximo teste de ponta
  a ponta. Varredura genérica por idade foi rejeitada por mérito: os dois maiores
  consumidores não moram no diretório de cache, e ela apagaria o browser atual de
  quem não roda teste há um mês.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from panlabs.heartbeat.config import Desired, DesiredStep
from panlabs.heartbeat.model import CacheVersion, Observed
from panlabs.plan import Plan, PlanItem

__all__ = [
    "DROP_DIR",
    "DROP_FILE",
    "HOST_ACTIONS",
    "NOTIFY",
    "REPORT_STEP",
    "RUN_ON_HOST",
    "RUN_STEP",
    "plan",
    "standing_order",
]

RUN_STEP = "run-step"
REPORT_STEP = "report-step"
DROP_DIR = "drop-dir"
DROP_FILE = "drop-file"
RUN_ON_HOST = "run-on-host"
NOTIFY = "notify"

HOST_ACTIONS = (RUN_ON_HOST,)
"""As ações que nenhum applier **deste lado** realiza, e o motivo.

Elas são do ramo parado, e o ramo parado é aquele em que não existe WSL onde
rodar nada: realizá-las daqui exigiria que o WSL estivesse de pé, e aí elas não
poderiam rodar. Elas atravessam a fronteira como ordem permanente e o applier do
host as despacha pelo nome do passo.

Registrar um efeito para elas aqui seria convidar exatamente o ato que a fronteira
de plataforma proíbe. Um teste garante que nenhuma tem efeito registrado, e que
todas as outras têm.
"""

HOST_DISK = "disco do host"
RUN_MARK = "marca de execução"
WSL_STATE = "estado do WSL"


def plan(observed: Observed, desired: Desired) -> Plan:
    """De estado observado e dado desejado para plano. Sem efeito, sem exceção.

    **Os alarmes vêm primeiro, e a ordem é decisão.** O plano é aplicado de cima
    para baixo, e um passo que trava seguraria para sempre um alarme que estivesse
    embaixo dele. O disco do host é justamente a métrica que ninguém mais vigia.
    """
    items: list[PlanItem] = []
    items.extend(_alarm_items(observed, desired))
    items.extend(_step_items(observed, desired))
    return Plan(items=tuple(items))


def standing_order(observed: Observed, desired: Desired) -> Plan:
    """O plano do ramo parado, emitido enquanto o WSL ainda está de pé.

    O ramo parado tem uma propriedade incômoda e inescapável: ele só é executável
    exatamente quando este planner é inalcançável, porque entrar no WSL para
    planejar seria **ligá-lo**, que é a única coisa que este desenho promete nunca
    fazer. A saída não é duplicar a decisão do outro lado da fronteira: é emitir a
    ordem de véspera, do mesmo planner puro, e deixar o host apenas realizá-la.

    Um plano já é artefato serializável neste repo, então a ordem permanente é o
    próprio `Plan` atravessando a fronteira de plataforma. O host executa e apaga:
    uma ordem vale uma vez, e quem a reemite é este planner, no disparo seguinte.

    Ela carrega **só os passos**. Os alarmes já saíram no plano vivo, e repeti-los
    de véspera notificaria duas vezes o mesmo fato.
    """
    if observed.wsl_running is not True:
        return Plan()
    return Plan(items=tuple(_step_items(replace(observed, wsl_running=False), desired)))


# --- os alarmes, e um canal por natureza de falha -----------------------------


def _alarm_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    items: list[PlanItem] = []
    items.extend(_unobserved_items(observed, desired))
    items.extend(_floor_items(observed, desired))
    items.extend(_stale_items(observed, desired))
    return items


def _unobserved_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    """Uma dimensão que não pôde ser observada é falha, e não ausência de notícia.

    Ela sai no canal de falha e **não** no canal do disco, mesmo quando o que
    faltou medir foi o disco. Um alarme de piso que na verdade significa "ninguém
    mediu" gastaria o único canal que vigia a métrica invisível de dentro do WSL.
    """
    if desired.unobserved is None:
        return []

    items: list[PlanItem] = []
    if observed.wsl_running is None:
        items.append(
            _notify(
                target=WSL_STATE,
                alarm=desired.unobserved.alarm,
                reason=(
                    f"{desired.unobserved.why}; o ramo não foi consultado, e nenhum passo "
                    "roda sem ele: tratar não consultado como parado compactaria um disco vivo"
                ),
            )
        )
    if desired.host_floor is not None and not observed.host.measured:
        items.append(
            _notify(
                target=HOST_DISK,
                alarm=desired.unobserved.alarm,
                reason=(
                    f"{desired.unobserved.why}; o disco do host não foi medido, então o piso "
                    "não pôde ser verificado. Esta métrica não existe de dentro do WSL"
                ),
            )
        )
    return items


def _floor_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    if desired.host_floor is None or not observed.host.measured:
        return []
    if observed.host.free_bytes >= desired.host_floor.free_bytes:
        return []
    return [
        _notify(
            target=HOST_DISK,
            alarm=desired.host_floor.alarm,
            reason=(
                f"{_gigabytes(observed.host.free_bytes)} livres, abaixo do piso de "
                f"{_gigabytes(desired.host_floor.free_bytes)}; {desired.host_floor.why}"
            ),
        )
    ]


def _stale_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    """A marca velha, e por que a marca ausente **não** é alarme.

    Ausente é o primeiro disparo. Alarmar nele treinaria o operador a ignorar o
    canal logo na estreia, que é o oposto do que "silencioso quando saudável"
    compra. O disparo seguinte já escreve a marca.
    """
    if desired.stale_mark is None or observed.last_run is None:
        return []
    age = _days_between(observed.last_run, observed.now)
    if age < desired.stale_mark.after_days:
        return []
    return [
        _notify(
            target=RUN_MARK,
            alarm=desired.stale_mark.alarm,
            reason=(
                f"a última execução foi há {age:.0f} dia(s), acima dos "
                f"{desired.stale_mark.after_days} tolerados; {desired.stale_mark.why}"
            ),
        )
    ]


def _notify(*, target: str, alarm: str, reason: str) -> PlanItem:
    return PlanItem(
        action=NOTIFY,
        target=target,
        reason=reason,
        payload={"alarm": alarm, "message": f"{target}: {reason}"},
    )


# --- os passos: ramo, cadência, e o corpo que cada um declara -----------------


def _step_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    if desired.steps is None or observed.branch is None:
        return []

    items: list[PlanItem] = []
    for step in desired.steps:
        if step.branch != observed.branch:
            continue
        due = _due(observed, step)
        if not due:
            continue
        items.extend(_body_items(observed, step, due))
    return items


def _due(observed: Observed, step: DesiredStep) -> str:
    """O motivo pelo qual a cadência deste passo venceu. Vazio quando não venceu.

    O motivo sai daqui pronto porque ele é metade do que torna o plano revisável:
    "roda o npm" sem dizer que a última vez foi há oito dias não é revisável.
    """
    mark = observed.mark(step.name)
    if mark.at is None:
        return f"nunca rodou, e a cadência dele é de {step.every_days} dia(s)"
    age = _days_between(mark.at, observed.now)
    if age < step.every_days:
        return ""
    return f"a última vez foi há {age:.0f} dia(s), e a cadência dele é de {step.every_days}"


def _body_items(observed: Observed, step: DesiredStep, due: str) -> list[PlanItem]:
    if step.on_host:
        return [
            PlanItem(
                action=RUN_ON_HOST,
                target=step.name,
                reason=f"{step.why}; {due}",
                payload={"step": step.name, "alarm": step.alarm, "branch": step.branch},
            )
        ]
    if step.run:
        return [
            PlanItem(
                action=RUN_STEP,
                target=step.name,
                reason=f"{step.why}; {due}",
                payload={
                    "step": step.name,
                    "run": list(step.run),
                    "alarm": step.alarm,
                    "branch": step.branch,
                },
            )
        ]
    if step.report is not None:
        return _report_items(step, due)
    if step.keep_newest is not None:
        return _keep_newest_items(observed, step)
    return _drop_matching_items(observed, step)


def _report_items(step: DesiredStep, due: str) -> list[PlanItem]:
    """O passo que relata pelo código de saída, com o mapa inteiro no item.

    O mapa atravessa porque o código só existe depois de o comando rodar: o
    applier não escolhe canal, ele consulta a tabela que este planner escreveu.
    As chaves vão como texto porque um plano é artefato serializável, e um mapa
    que muda de forma ao passar por JSON quebraria em produção e não no teste.

    O canal do passo continua no item e não é redundante: ele é o canal do que o
    mapa **não** cobre, que é falha do próprio passo -- desde o comando que não
    existe até um código que ninguém previu.
    """
    report = step.report
    assert report is not None
    return [
        PlanItem(
            action=REPORT_STEP,
            target=step.name,
            reason=f"{step.why}; {due}",
            payload={
                "step": step.name,
                "run": list(report.command),
                "codes": {str(code): alarm for code, alarm in sorted(report.codes.items())},
                "alarm": step.alarm,
                "branch": step.branch,
            },
        )
    ]


def _keep_newest_items(observed: Observed, step: DesiredStep) -> list[PlanItem]:
    """Mantém as revisões novas de cada família e planeja a remoção das velhas.

    Uma família com uma revisão só nunca perde nada: a regra é "existe coisa mais
    nova", não "isto é antigo". É essa diferença que impede a poda de apagar o
    browser atual de um produto que só tem uma versão instalada.
    """
    wanted = step.keep_newest
    assert wanted is not None
    mine = [entry for entry in observed.versions if entry.root == wanted.root]

    items: list[PlanItem] = []
    for family in sorted({entry.family for entry in mine}):
        ranked = sorted(
            (entry for entry in mine if entry.family == family),
            key=lambda entry: entry.version,
            reverse=True,
        )
        kept, obsolete = ranked[: wanted.keep], ranked[wanted.keep :]
        if not obsolete:
            continue
        newest = _version(kept[0]) if kept else "nenhuma"
        for entry in reversed(obsolete):
            items.append(
                PlanItem(
                    action=DROP_DIR,
                    target=entry.path,
                    reason=(
                        f"{step.why}; `{family}` já tem a revisão {newest} instalada, e esta "
                        f"é a {_version(entry)}, ocupando {_gigabytes(entry.bytes)}"
                    ),
                    payload={"step": step.name, "path": entry.path, "alarm": step.alarm},
                )
            )
    return items


def _drop_matching_items(observed: Observed, step: DesiredStep) -> list[PlanItem]:
    wanted = step.drop_matching
    assert wanted is not None
    mine = sorted(
        (entry for entry in observed.leftovers if entry.root == wanted.root),
        key=lambda entry: entry.path,
    )
    return [
        PlanItem(
            action=DROP_FILE,
            target=entry.path,
            reason=f"{step.why}; termina em `{wanted.suffix}` e ocupa {_gigabytes(entry.bytes)}",
            payload={"step": step.name, "path": entry.path, "alarm": step.alarm},
        )
        for entry in mine
    ]


# --- as unidades em que o operador lê o plano ---------------------------------


def _days_between(start: datetime, end: datetime) -> float:
    """Em dias fracionários, e não em dias inteiros.

    `timedelta.days` trunca, então uma marca de 6,9 dias contra uma cadência de 7
    venceria por arredondamento. A cadência é a promessa que o passo faz; ela não
    pode vencer meio dia antes por causa da unidade em que alguém a leu.
    """
    return (end - start).total_seconds() / 86_400


def _version(entry: CacheVersion) -> str:
    return ".".join(str(part) for part in entry.version)


def _gigabytes(size: int) -> str:
    if size <= 0:
        return "tamanho não medido"
    return f"{size / 1_000_000_000:.2f} GB"
