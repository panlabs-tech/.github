"""Os efeitos do heartbeat: um ato por ação, e nenhuma decisão.

Duas coisas aqui merecem explicação, porque nenhuma delas é decisão disfarçada.

**A falha de um passo é capturada, e não propagada.** Três passos independentes
não são uma corrente: um `npm` que falhou não pode impedir a poda do browser de
rodar, e muito menos engolir um alarme de disco que estava embaixo dele no plano.
O canal em que a falha é reportada **não** é escolhido aqui: ele veio no `payload`,
escrito pelo planner a partir do que o passo declarou.

**As marcas são gravadas uma vez, no fim.** A marca da própria execução é gravada
**sempre**, inclusive quando o plano saiu vazio: ela é o que o vigia de homem-morto
lê, e uma máquina saudável que não escrevesse marca ficaria indistinguível de uma
tarefa morta. É o oposto exato do que este heartbeat existe para garantir.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from panlabs.heartbeat.observe import MARKS_FILE, read_marks
from panlabs.heartbeat.planner import DROP_DIR, DROP_FILE, NOTIFY, RUN_STEP
from panlabs.plan import Effect, Plan, PlanItem

__all__ = [
    "ALARMS_FILE",
    "LOG_FILE",
    "STANDING_ORDER_FILE",
    "Alarm",
    "Runner",
    "build_runner",
    "run_command",
    "write_standing_order",
]

ALARMS_FILE = "alarms.json"
LOG_FILE = "heartbeat.log"
STANDING_ORDER_FILE = "standing-order.json"

Run = Callable[[Sequence[str]], tuple[int, str]]
"""Roda um comando e devolve o código de saída e o que ele disse."""


@dataclass(frozen=True)
class Alarm:
    """Um alarme pronto para o host tocar: o canal, e o texto."""

    alarm: str
    message: str


def run_command(command: Sequence[str]) -> tuple[int, str]:
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return done.returncode, (done.stderr or done.stdout or "").strip()[:400]


@dataclass
class Runner:
    """Os efeitos, mais a lembrança do que rodou e do que falhou.

    Ele lembra porque precisa: a marca de um passo só é gravada se ele deu certo
    **por inteiro**, senão um passo que falha em silêncio ganharia mais uma semana
    de folga a cada tentativa; e o código de saída do processo precisa dizer se
    houve falha, porque quem chama do lado do host lê isso.
    """

    state_dir: Path
    now: datetime
    run: Run
    log: Callable[[str], None]
    stamped: set[str] = field(default_factory=set)
    alarms: list[Alarm] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def landed(self) -> set[str]:
        """Os passos que podem receber marca: os que deram certo **por inteiro**.

        Um passo vira vários itens quando poda um cache: quatro revisões velhas de
        browser são quatro remoções do mesmo passo. Se uma falha e três dão certo,
        marcar o passo daria à que falhou mais uma semana de folga, e ela voltaria
        a falhar calada. Um passo só está feito quando nenhuma parte dele falhou.
        """
        return self.stamped - set(self.failed)

    @property
    def effects(self) -> dict[str, Effect]:
        return {
            RUN_STEP: self._run_step,
            DROP_DIR: self._drop_dir,
            DROP_FILE: self._drop_file,
            NOTIFY: self._notify,
        }

    def commit(self) -> None:
        """Grava marcas e alarmes de uma vez só, e a da própria execução sempre.

        Os alarmes **substituem** o arquivo em vez de acrescentar: quem os toca é o
        host, logo em seguida, e um arquivo acumulado tocaria de novo o alarme da
        semana passada. Uma execução saudável escreve uma lista vazia, que é como
        "silencioso" fica escrito em disco.
        """
        marks = read_marks(self.state_dir)
        steps: dict[str, Any] = dict(marks.get("steps") or {})
        steps.update({step: self.now.isoformat() for step in sorted(self.landed)})

        self._write(
            MARKS_FILE, {"last_run": self.now.isoformat(), "steps": dict(sorted(steps.items()))}
        )
        self._write(ALARMS_FILE, [{"alarm": a.alarm, "message": a.message} for a in self.alarms])

    # --- um ato por ação ------------------------------------------------------

    def _run_step(self, item: PlanItem) -> None:
        command = [str(part) for part in item.payload["run"]]
        code, said = self.run(command)
        if code == 0:
            self._done(item, f"rodou `{' '.join(command)}`")
            return
        self._failed(item, f"`{' '.join(command)}` saiu com código {code}: {said}")

    def _drop_dir(self, item: PlanItem) -> None:
        try:
            shutil.rmtree(item.payload["path"])
        except OSError as exc:
            self._failed(item, f"não removeu o diretório: {exc}")
            return
        self._done(item, f"removeu {item.target}")

    def _drop_file(self, item: PlanItem) -> None:
        try:
            Path(str(item.payload["path"])).unlink()
        except OSError as exc:
            self._failed(item, f"não removeu o arquivo: {exc}")
            return
        self._done(item, f"removeu {item.target}")

    def _notify(self, item: PlanItem) -> None:
        self._raise(str(item.payload["alarm"]), str(item.payload["message"]))

    # --- e o registro do que aconteceu ---------------------------------------

    def _done(self, item: PlanItem, said: str) -> None:
        self.stamped.add(str(item.payload["step"]))
        self.log(f"ok    {item.action}  {item.target}: {said}")

    def _failed(self, item: PlanItem, said: str) -> None:
        step = str(item.payload["step"])
        self.failed.append(step)
        self.log(f"falha {item.action}  {item.target}: {said}")
        self._raise(str(item.payload["alarm"]), f"{step}: {said}")

    def _raise(self, alarm: str, message: str) -> None:
        self.alarms.append(Alarm(alarm=alarm, message=message))
        self.log(f"alarme[{alarm}] {message}")

    def _write(self, name: str, body: object) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / name).write_text(
            json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


def write_standing_order(order: Plan, state_dir: Path) -> None:
    """Deixa para o host o plano do ramo parado, ou apaga o que ficou obsoleto.

    Reemitir a cada disparo é o que mantém a ordem fresca sem que o host precise
    julgar idade: se o passo do ramo parado não vence mais, a ordem some, e o host
    simplesmente não encontra nada para fazer. É a alternativa a transcrever a
    cadência do outro lado da fronteira, que duplicaria a decisão em PowerShell.
    """
    path = state_dir / STANDING_ORDER_FILE
    if not order:
        path.unlink(missing_ok=True)
        return
    state_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(order.to_json() + "\n", encoding="utf-8")


def build_runner(*, state_dir: Path, now: datetime, run: Run | None = None) -> Runner:
    """O runner amarrado ao diretório de estado em que tem permissão de escrever.

    `run` é resolvido na chamada, e não amarrado no default: um default avaliado na
    definição fixaria o executor para sempre, e o teste que exercita a fiação
    inteira precisa poder trocá-lo sem trocar a fiação.
    """

    def log(line: str) -> None:
        state_dir.mkdir(parents=True, exist_ok=True)
        with (state_dir / LOG_FILE).open("a", encoding="utf-8") as handle:
            handle.write(f"{now.isoformat()}  {line}\n")

    return Runner(state_dir=state_dir, now=now, run=run or run_command, log=log)
