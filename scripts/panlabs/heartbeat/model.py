"""O estado observado pelo heartbeat, depois de o JSON cru virar tipo.

Três coisas aqui carregam quase toda a issue:

**O ramo é uma leitura da observação, não uma decisão.** Poda exige o WSL de pé;
compactação exige o WSL parado. Quem diz em qual dos dois a máquina está é a
consulta ao host, e `branch` é só o nome dela.

**"De pé" e "parado" não esgotam o mundo: existe "não consultado".** Tratar não
consultado como parado rodaria a compactação contra um disco vivo, que é o único
ato que este desenho nunca pode cometer. Por isso `wsl_running` é tri-estado, e o
planner não planeja passo nenhum sem saber em qual ramo está.

**O disco do host é medido ou não é.** Não medido com `free_bytes` em zero
dispararia o alarme de piso justamente quando ninguém mediu nada. Um alarme falso
nesse canal é caro: ele é o único vigia de uma métrica que não se enxerga de
dentro do WSL, e treinar o operador a ignorá-lo custaria o disco.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

__all__ = [
    "BRANCHES",
    "BRANCH_DOWN",
    "BRANCH_UP",
    "CacheVersion",
    "HostDisk",
    "LeftoverFile",
    "Mark",
    "Observed",
]

BRANCH_UP = "wsl-up"
BRANCH_DOWN = "wsl-down"
BRANCHES = (BRANCH_UP, BRANCH_DOWN)
"""Os dois ramos, e eles são exaustivos por construção.

Um passo declara em qual roda, e é isso que permite o checker de conformidade da
spec de Repo #4 entrar como passo sem que a tarefa seja reescrita: ele é do ramo
de cima, junto da poda, e o dado o diz.
"""


@dataclass(frozen=True)
class HostDisk:
    """O disco do host, a única métrica que não se mede de dentro do WSL.

    `measured` existe porque o disco virtual é *thin-provisioned*: de dentro, o
    sistema reporta centenas de GB que fisicamente não existem. A medição só vale
    se veio do host, e uma que não veio precisa ser distinguível de uma que veio
    com o disco cheio.
    """

    measured: bool = False
    free_bytes: int = 0
    total_bytes: int = 0


@dataclass(frozen=True)
class Mark:
    """A última vez que um passo rodou. Sem data, ele nunca rodou."""

    step: str
    at: datetime | None = None


@dataclass(frozen=True)
class CacheVersion:
    """Uma revisão de um cache que versiona por diretório.

    `family` inclui o caminho relativo até o pai, e não só o prefixo do nome: dois
    produtos diferentes do mesmo cache usam o mesmo prefixo (`chrome/linux-148` e
    `chrome-headless-shell/linux-148`), e agrupá-los pelo prefixo faria a poda
    apagar o browser atual de um deles por engano.

    `version` é tupla de inteiros para que `1223` fique acima de `1161` e
    `148.0.7778.97` acima de `127.0.6533.72`, sem ordenação alfabética.
    """

    root: str
    family: str
    version: tuple[int, ...]
    path: str
    bytes: int = 0


@dataclass(frozen=True)
class LeftoverFile:
    """Um arquivo de instalação que sobrou depois de extraído."""

    root: str
    path: str
    bytes: int = 0


@dataclass(frozen=True)
class Observed:
    """O retrato que o planner recebe. Nada aqui é decisão.

    `now` entra como observação e não como relógio de dentro do planner, porque a
    cadência é aritmética sobre o tempo e um planner que lê o relógio deixa de ser
    puro. É o mesmo motivo de o estado observado poder virar fixture.
    """

    now: datetime
    wsl_running: bool | None = None
    host: HostDisk = HostDisk()
    last_run: datetime | None = None
    marks: tuple[Mark, ...] = ()
    versions: tuple[CacheVersion, ...] = ()
    leftovers: tuple[LeftoverFile, ...] = ()

    @property
    def branch(self) -> str | None:
        """Em qual ramo a máquina está agora. `None` é "não consultado"."""
        if self.wsl_running is None:
            return None
        return BRANCH_UP if self.wsl_running else BRANCH_DOWN

    def mark(self, step: str) -> Mark:
        for entry in self.marks:
            if entry.step == step:
                return entry
        return Mark(step=step)
