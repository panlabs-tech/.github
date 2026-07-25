"""Onde toda decisão sobre o equipamento da máquina mora. Puro, testado.

Cinco dimensões, e cada uma tem uma decisão que não é óbvia:

- **links**: um nome só conta como alcançável se resolve pelo nome real. Alias de
  shell não existe em subprocesso, que é como o agente roda, então alias é
  ausência para este planner.
- **retire**: um diretório cuja remoção está decidida fica **retido** enquanto
  algum nome que precisa ser alcançável ainda resolve dentro dele. É o que impede
  o plano de agrupar a remoção do runtime vivo com as outras remoções.
- **read_denylist**: a negação vale sempre sobre o **alvo resolvido**. Negar o
  nome escrito bloqueia a ferramenta e deixa o comando de terminal passar, porque
  o shell fala com o alvo. Medido, não deduzido.
- **statusline**: um comando que baixa pacote a cada render é divergente por si,
  independentemente de qual pacote seja.
- **skills**: uma skill candidata a global não existe em repo nenhum. Quem está
  sendo promovida agora já conta como global, senão promover criaria a inversão
  de precedência que a cláusula existe para dissolver.

O que este planner **não** decide: nada sobre o espaço de trabalho (issue #21) e
nada sobre o heartbeat (issue #22). Ele lê a máquina e para no equipamento.
"""

from __future__ import annotations

from panlabs.machine.config import Desired, DesiredRetire, DesiredSkills
from panlabs.machine.model import CredentialPath, Observed
from panlabs.plan import Plan, PlanItem

__all__ = [
    "DENY_READ",
    "DISCARD_SKILL",
    "DROP_VENDORED_SKILL",
    "LINK_NAME",
    "PIN_STATUSLINE",
    "PROMOTE_SKILL",
    "RETIRE_DIR",
    "plan",
]

LINK_NAME = "link-name"
RETIRE_DIR = "retire-dir"
DENY_READ = "deny-read"
PIN_STATUSLINE = "pin-statusline"
PROMOTE_SKILL = "promote-skill"
DISCARD_SKILL = "discard-skill"
DROP_VENDORED_SKILL = "drop-vendored-skill"

DEVENDOR_HOLD = (
    "remover arquivo versionado de dentro de um repositório é o retrofit da spec de Repo #4, "
    "que é onde a spec de Máquina #3 põe essa remoção; o item aparece para ser lido"
)

DISCARD_HOLD = (
    "descartar é a decisão de **não** promover, e ela já está realizada por esta skill "
    "não existir no global; apagar o arquivo no repo é o retrofit da spec de Repo #4"
)

MANUAL_ACTIONS = (PROMOTE_SKILL, DISCARD_SKILL, DROP_VENDORED_SKILL)
"""As ações que nenhum applier realiza, e o motivo de cada uma não ser daqui.

Promover é da **CLI de distribuição**: ela é o único mecanismo de instalação de
skill, e um efeito que copiasse diretório deixaria a skill global sem upstream de
onde atualizar, que é exatamente o que a decisão de usar a CLI evita. O plano
carrega o comando exato, e quem o roda é a CLI.

Descartar e des-vendorizar são da spec de Repo #4, que é onde a spec de Máquina #3
põe a remoção de arquivo versionado de dentro de um repositório.

Um teste garante que estas três não têm efeito e que todas as outras têm.
"""

PROMOTE_HOLD = (
    "instalar skill é da CLI de distribuição, que é o único mecanismo; copiar "
    "diretório deixaria a skill global sem upstream de onde atualizar"
)


def plan(observed: Observed, desired: Desired) -> Plan:
    """De estado observado e dado desejado para plano. Sem efeito, sem exceção.

    A ordem das dimensões é a ordem de leitura do plano, e é deliberada: os links
    vêm antes das remoções porque é essa a sequência que não pode ser invertida, e
    um plano que a mostra ao contrário convidaria ao erro mesmo com o `hold` no
    lugar.
    """
    items: list[PlanItem] = []
    items.extend(_link_items(observed, desired))
    items.extend(_retire_items(observed, desired))
    items.extend(_deny_items(observed, desired))
    items.extend(_statusline_items(observed, desired))
    items.extend(_skill_items(observed, desired))
    return Plan(items=tuple(items))


# --- nomes alcançáveis em subprocesso ----------------------------------------


def _link_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    if desired.links is None or desired.bin_dir is None:
        return []

    items: list[PlanItem] = []
    for wanted in desired.links:
        current = observed.link(wanted.name)
        if current.points_to == wanted.target:
            continue
        where = "não existe" if not current.present else f"aponta para {current.points_to}"
        items.append(
            PlanItem(
                action=LINK_NAME,
                target=f"{desired.bin_dir}/{wanted.name}",
                reason=f"{wanted.why}; hoje {where}",
                payload={"target": wanted.target, "name": wanted.name},
            )
        )
    return items


# --- remoções, e a única que precisa esperar ---------------------------------


def _retire_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    if desired.retire is None:
        return []

    present = {entry.path: entry for entry in observed.retire}
    items: list[PlanItem] = []
    for wanted in desired.retire:
        observed_dir = present.get(wanted.path)
        if observed_dir is None or not observed_dir.present:
            continue
        items.append(
            PlanItem(
                action=RETIRE_DIR,
                target=wanted.path,
                reason=f"{wanted.why} ({_gigabytes(observed_dir.bytes)})",
                payload={"path": wanted.path},
                hold=_retire_hold(observed, desired, wanted),
            )
        )
    return items


def _retire_hold(observed: Observed, desired: Desired, wanted: DesiredRetire) -> str:
    """Retém a remoção enquanto algo que precisa ser alcançável mora lá dentro.

    Este é o sequenciamento que não pode ser invertido, escrito como decisão do
    planner em vez de confiado à ordem em que alguém lê o plano. O nome que ainda
    resolve lá dentro entra no texto, porque "retido" sem dizer por quem não é
    revisável.
    """
    if desired.links is None:
        return ""

    hostages = sorted(
        wanted_link.name
        for wanted_link in desired.links
        if _inside(observed.link(wanted_link.name).resolved, wanted.path)
    )
    if not hostages:
        return ""
    return (
        f"{', '.join(hostages)} ainda resolve dentro de {wanted.path}; "
        "remover antes da migração deixaria a máquina sem runtime"
    )


def _inside(path: str, directory: str) -> bool:
    return bool(path) and (path == directory or path.startswith(f"{directory}/"))


def _gigabytes(size: int) -> str:
    if size <= 0:
        return "tamanho não medido"
    return f"{size / 1_000_000_000:.2f} GB"


# --- negação de leitura sobre o alvo resolvido -------------------------------


def _deny_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    if desired.read_denylist is None:
        return []

    seen = {entry.path: entry for entry in observed.credentials}
    already = set(observed.denylist)
    planned: set[str] = set()
    items: list[PlanItem] = []

    for wanted in desired.read_denylist:
        found = seen.get(wanted.path)
        if found is None or not found.present:
            continue

        entry = _deny_entry(found)
        if entry in already or found.resolved in planned:
            continue

        planned.add(found.resolved)
        items.append(
            PlanItem(
                action=DENY_READ,
                target=found.resolved,
                reason=f"{wanted.why}; {_radius(found)}",
                payload={"entry": entry},
            )
        )
    return items


def _deny_entry(found: CredentialPath) -> str:
    """A forma da entrada de negação, derivada do alvo resolvido e do seu tipo.

    Diretório recebe o sufixo recursivo; arquivo não pode receber, porque um
    padrão recursivo sobre arquivo não casa com nada e a negação silenciosamente
    não valeria. É o tipo de erro que só aparece quando alguém tenta ler.
    """
    if found.is_dir:
        return f"Read(//{found.resolved.lstrip('/')}/**)"
    return f"Read(//{found.resolved.lstrip('/')})"


def _radius(found: CredentialPath) -> str:
    """Diz se este item cobre credencial que existe ou é antecipação.

    O raio real desta postura são as credenciais que estão lá. Um plano que trata
    diretório vazio e cofre cheio com o mesmo texto infla o raio, e a spec é
    explícita em não fazer isso.
    """
    if found.entries == 0:
        return "diretório vazio hoje: negado por antecipação, fora do raio real"

    leak = ""
    if found.is_linked:
        leak = f"; alcançado por link em {found.path}, e negar o link vaza pelo shell"
    return f"{found.entries} entrada(s) hoje{leak}"


# --- a barra de status ---------------------------------------------------------


def _statusline_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    if desired.statusline is None or observed.statusline == desired.statusline:
        return []

    what = "baixa um pacote a cada render" if _fetches(observed.statusline) else "está divergente"
    return [
        PlanItem(
            action=PIN_STATUSLINE,
            target="statusLine",
            reason=f"`{observed.statusline}` {what}; o desejado é `{desired.statusline}`",
            payload={"command": desired.statusline},
        )
    ]


def _fetches(command: str) -> bool:
    """Um comando que resolve pacote na rede a cada render, e por isso custa."""
    return "npx " in f" {command}" or "@latest" in command


# --- zero redundância de skills -----------------------------------------------


def _skill_items(observed: Observed, desired: Desired) -> list[PlanItem]:
    if desired.skills is None:
        return []

    wanted = desired.skills
    # Chaveado por repo **e** nome: a mesma skill existe em vários repos, e a
    # origem da cópia global não pode depender da ordem em que o disco foi lido.
    vendored = {(entry.repo, entry.name): entry for entry in observed.vendored_skills}
    items: list[PlanItem] = []

    for move in wanted.promote:
        if move.name in observed.global_skills:
            continue
        source = vendored.get((move.source, move.name))
        if source is None:
            continue
        items.append(
            PlanItem(
                action=PROMOTE_SKILL,
                target=move.name,
                reason=f"{move.why}; sobe de {source.repo} para o global",
                payload={
                    "name": move.name,
                    "from": source.path,
                    "command": (
                        f"npx skills add panlabs-tech/skills --global --skill {move.name} --yes"
                    ),
                },
                hold=PROMOTE_HOLD,
            )
        )

    for move in wanted.discard:
        source = vendored.get((move.source, move.name))
        if source is None:
            continue
        items.append(
            PlanItem(
                action=DISCARD_SKILL,
                target=move.name,
                reason=(
                    f"{move.why}; é revisão anterior de `{move.superseded_by}`, que já é global, "
                    "e promovê-la criaria duas globais para o mesmo trabalho"
                ),
                payload={"name": move.name, "path": source.path},
                hold=DISCARD_HOLD,
            )
        )

    items.extend(_devendor_items(observed, wanted))
    return items


def _devendor_items(observed: Observed, wanted: DesiredSkills) -> list[PlanItem]:
    """A varredura: nenhuma skill candidata a global existe em repo nenhum.

    Quem está sendo promovida nesta rodada já conta como global, porque a colisão
    de nome nasce no instante da promoção, não na rodada seguinte. Uma skill que
    só existe num repo e não tem par global não é candidata e não é tocada: a
    cláusula é sobre colisão, não sobre proibir skill local.

    Todo item sai **retido**, sem exceção. A varredura é desta issue; a remoção do
    arquivo é o retrofit da spec de Repo #4, que é onde a spec de Máquina #3 a
    coloca. O item continua no plano porque a varredura só vale se for legível por
    inteiro: esconder a frota faria o plano mentir sobre a redundância que existe.
    """
    global_names = set(observed.global_skills)
    global_names.update(move.name for move in wanted.promote)
    discarded = {move.name for move in wanted.discard}

    items: list[PlanItem] = []
    for entry in observed.vendored_skills:
        if entry.name in discarded or entry.name not in global_names:
            continue
        items.append(
            PlanItem(
                action=DROP_VENDORED_SKILL,
                target=entry.path,
                reason=(
                    f"`{entry.name}` é global; a cópia em {entry.repo} colide por nome "
                    "e a cópia global é a única"
                ),
                payload={"name": entry.name, "path": entry.path, "repo": entry.repo},
                hold=DEVENDOR_HOLD,
            )
        )
    return items
