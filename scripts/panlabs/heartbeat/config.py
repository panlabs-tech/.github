"""A configuração desejada do heartbeat: dado versionado, carregado de arquivo.

Os valores são decididos pela spec de Máquina #3 e vivem em `config/heartbeat.json`.
Este módulo entrega o esqueleto do dado e a sua leitura, nunca os valores.

**Um passo é dado, e é isso que o torna plugável.** Ele declara o ramo em que
roda, a cadência que é dele, o canal de alarme que é dele, e o corpo do que faz.
Plugar um passo cujo **corpo já existe** é acrescentar uma entrada nesta lista e,
se for o caso, um canal na outra: nenhuma linha de código muda, que é exatamente o
que "sem reescrita" quer dizer.

**O checker de conformidade da spec de Repo #4 não foi esse caso, e o dado
prometia que seria.** Ele precisa de um corpo que traduza **código de saída em
canal**, porque o corpo `run` trata todo código diferente de zero como falha, no
canal único do passo: com um canal só, token expirado chegaria como deriva de
anatomia, que é o disfarce que este desenho existe para impedir. Corpo novo é
capacidade nova, e não configuração, então ele custou código -- e é assim mesmo.

**Todo canal de alarme é declarado.** Um passo que nomeasse um canal inexistente
falharia calado no lugar mais caro: o alarme sairia no canal errado, e o desenho
inteiro existe para que falha de rede num passo não se disfarce de alarme de disco.
Por isso a leitura recusa o dado em vez de aceitar e torcer.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from panlabs.heartbeat.model import BRANCH_DOWN, BRANCHES

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "Desired",
    "DesiredChannel",
    "DesiredFloor",
    "DesiredStale",
    "DesiredStep",
    "DesiredUnobserved",
    "DropMatching",
    "KeepNewest",
    "Report",
    "expand",
    "load_desired",
]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "heartbeat.json"

KNOWN_KEYS = ("channels", "host_floor", "stale_mark", "unobserved", "steps")


def expand(path: str) -> str:
    """`~/x` vira o caminho absoluto desta máquina, sem resolver link nenhum."""
    return str(Path(path).expanduser())


@dataclass(frozen=True)
class DesiredChannel:
    """Um canal de alarme, com o que ele significa quando toca."""

    name: str
    why: str


@dataclass(frozen=True)
class DesiredFloor:
    """O piso do disco do host: abaixo dele, notifica."""

    free_bytes: int
    alarm: str
    why: str


@dataclass(frozen=True)
class DesiredStale:
    """A idade a partir da qual a marca de execução vira alarme."""

    after_days: int
    alarm: str
    why: str


@dataclass(frozen=True)
class DesiredUnobserved:
    """O canal em que uma dimensão que não pôde ser observada é reportada.

    Ela é **falha**, e não ausência de notícia: o disco chegou a 99% precisamente
    porque o silêncio e a saúde eram indistinguíveis.
    """

    alarm: str
    why: str


@dataclass(frozen=True)
class KeepNewest:
    """Um cache que versiona por diretório, e quantas revisões ficam.

    O reenquadramento que faz a poda funcionar: o desperdício não é browser, é
    versão velha de browser. Manter a mais nova custa quase nada e não quebra o
    próximo teste de ponta a ponta.
    """

    root: str
    keep: int = 1


@dataclass(frozen=True)
class DropMatching:
    """Arquivos órfãos, reconhecidos pela forma do nome, nunca pela idade.

    Por forma e não por idade porque idade é o critério que a spec rejeitou **por
    mérito**: uma varredura por idade apagaria o browser atual de quem não roda
    teste de ponta a ponta há um mês, e erraria os dois maiores consumidores, que
    nem moram no diretório de cache.
    """

    root: str
    suffix: str


@dataclass(frozen=True)
class Report:
    """Um comando cujo **código de saída é o relatório dele**, e o mapa dos códigos.

    Existe porque `run` só sabe dizer "deu certo" ou "falhou", num canal só. Um
    comando que distingue "achei deriva" de "não consegui observar" precisa que a
    distinção sobreviva até o alarme: com um canal único, um token expirado
    chegaria ao operador como deriva de anatomia da frota inteira.

    Um código declarado significa que o comando **rodou e relatou**: o passo
    cumpriu o que tinha para fazer, e o que varia é em qual canal o relatório sai.
    Um código não declarado é falha do próprio passo, e sai no canal dele.
    """

    command: tuple[str, ...]
    codes: Mapping[int, str]


@dataclass(frozen=True)
class DesiredStep:
    """Um passo do heartbeat: onde roda, quando roda, como alarma, e o que faz.

    Os cinco corpos são exclusivos entre si, e um passo tem exatamente um: rodar
    um comando nativo de limpeza, manter só as revisões novas de um cache
    versionado, remover arquivo órfão por forma de nome, rodar um comando cujo
    código de saída é o relatório dele, ou ser realizado **pelo host**, que é o
    caso do ramo parado, onde não existe WSL onde rodar nada.
    """

    name: str
    branch: str
    every_days: int
    alarm: str
    why: str
    run: tuple[str, ...] = ()
    keep_newest: KeepNewest | None = None
    drop_matching: DropMatching | None = None
    report: Report | None = None
    on_host: bool = False


@dataclass(frozen=True)
class Desired:
    """O estado desejado do heartbeat."""

    channels: tuple[DesiredChannel, ...] | None = None
    host_floor: DesiredFloor | None = None
    stale_mark: DesiredStale | None = None
    unobserved: DesiredUnobserved | None = None
    steps: tuple[DesiredStep, ...] | None = None

    @property
    def undecided(self) -> tuple[str, ...]:
        """As dimensões que ainda esperam decisão da spec de Máquina #3."""
        return tuple(sorted(key for key in KNOWN_KEYS if getattr(self, key) is None))

    @property
    def is_decided(self) -> bool:
        return not self.undecided

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Desired:
        unknown = sorted(k for k in raw if not k.startswith("_") and k not in KNOWN_KEYS)
        if unknown:
            raise ValueError(
                f"chave desconhecida na configuração desejada: {', '.join(unknown)}; "
                f"chaves válidas: {', '.join(KNOWN_KEYS)}"
            )

        channels = _channels(raw.get("channels"))
        desired = cls(
            channels=channels,
            host_floor=_floor(raw.get("host_floor")),
            stale_mark=_stale(raw.get("stale_mark")),
            unobserved=_unobserved(raw.get("unobserved")),
            steps=_steps(raw.get("steps")),
        )
        _check_alarms(desired)
        return desired


def _check_alarms(desired: Desired) -> None:
    """Todo canal nomeado precisa existir. Sem canais decididos, não há o que checar."""
    if desired.channels is None:
        return

    known = {channel.name for channel in desired.channels}
    named: list[tuple[str, str]] = []
    if desired.host_floor is not None:
        named.append((desired.host_floor.alarm, "host_floor"))
    if desired.stale_mark is not None:
        named.append((desired.stale_mark.alarm, "stale_mark"))
    if desired.unobserved is not None:
        named.append((desired.unobserved.alarm, "unobserved"))
    named.extend((step.alarm, f"passo `{step.name}`") for step in desired.steps or ())
    named.extend(
        (alarm, f"código {code} do passo `{step.name}`")
        for step in desired.steps or ()
        if step.report is not None
        for code, alarm in step.report.codes.items()
    )

    missing = sorted({f"`{alarm}` em {where}" for alarm, where in named if alarm not in known})
    if missing:
        raise ValueError(
            f"canal de alarme não declarado: {', '.join(missing)}; "
            f"canais declarados: {', '.join(sorted(known))}"
        )


def _require(entry: Mapping[str, Any], *keys: str, dimension: str) -> None:
    missing = sorted(k for k in keys if not entry.get(k))
    if missing:
        raise ValueError(
            f"entrada de `{dimension}` sem os campos que o planner usa: "
            f"{', '.join(missing)} em {entry!r}"
        )


def _channels(raw: Any) -> tuple[DesiredChannel, ...] | None:
    if raw is None:
        return None
    out: list[DesiredChannel] = []
    for entry in _entries(raw):
        _require(entry, "name", "why", dimension="channels")
        out.append(DesiredChannel(name=entry["name"], why=entry["why"]))
    return tuple(out)


def _floor(raw: Any) -> DesiredFloor | None:
    if raw is None:
        return None
    entry = _object(raw, dimension="host_floor")
    _require(entry, "free_bytes", "alarm", "why", dimension="host_floor")
    return DesiredFloor(free_bytes=int(entry["free_bytes"]), alarm=entry["alarm"], why=entry["why"])


def _stale(raw: Any) -> DesiredStale | None:
    if raw is None:
        return None
    entry = _object(raw, dimension="stale_mark")
    _require(entry, "after_days", "alarm", "why", dimension="stale_mark")
    return DesiredStale(after_days=int(entry["after_days"]), alarm=entry["alarm"], why=entry["why"])


def _unobserved(raw: Any) -> DesiredUnobserved | None:
    if raw is None:
        return None
    entry = _object(raw, dimension="unobserved")
    _require(entry, "alarm", "why", dimension="unobserved")
    return DesiredUnobserved(alarm=entry["alarm"], why=entry["why"])


def _steps(raw: Any) -> tuple[DesiredStep, ...] | None:
    if raw is None:
        return None
    out: list[DesiredStep] = []
    for entry in _entries(raw):
        _require(entry, "name", "branch", "every_days", "alarm", "why", dimension="steps")
        out.append(
            DesiredStep(
                name=entry["name"],
                branch=_branch(entry),
                every_days=int(entry["every_days"]),
                alarm=entry["alarm"],
                why=entry["why"],
                **_body(entry),
            )
        )
    _check_unique(out)
    _check_branch_body(out)
    return tuple(out)


def _check_branch_body(steps: Sequence[DesiredStep]) -> None:
    """No ramo parado, o corpo é do host. Não existe WSL onde rodar o resto.

    Esta é a única regra que amarra ramo e corpo, e ela não é zelo: um passo do
    ramo parado que declarasse um comando de dentro só poderia ser realizado
    ligando o WSL, e ligar o WSL é a única coisa que este desenho promete nunca
    fazer. Recusar o dado é mais barato do que descobrir isso no host, elevado.
    """
    for step in steps:
        if step.branch == BRANCH_DOWN and not step.on_host:
            raise ValueError(
                f"o passo `{step.name}` é do ramo `{BRANCH_DOWN}` e não declara `on_host`; "
                "com o WSL parado não existe onde rodar um comando de dentro, e realizá-lo "
                "exigiria ligá-lo"
            )
        if step.on_host and step.branch != BRANCH_DOWN:
            raise ValueError(
                f"o passo `{step.name}` declara `on_host` fora do ramo `{BRANCH_DOWN}`; "
                "o applier de dentro do WSL não realiza ato do host, e um passo assim "
                "ficaria planejado e nunca executado"
            )


def _check_unique(steps: Sequence[DesiredStep]) -> None:
    """Nome de passo é chave da marca de última execução, então repetir apaga cadência."""
    seen: set[str] = set()
    for step in steps:
        if step.name in seen:
            raise ValueError(
                f"passo repetido em `steps`: `{step.name}`; o nome é a chave da marca "
                "de última execução, e dois passos com o mesmo nome compartilhariam cadência"
            )
        seen.add(step.name)


def _branch(entry: Mapping[str, Any]) -> str:
    branch = str(entry["branch"])
    if branch not in BRANCHES:
        raise ValueError(
            f"ramo desconhecido em `steps`: `{branch}` no passo `{entry.get('name')}`; "
            f"ramos válidos: {', '.join(BRANCHES)}"
        )
    return branch


BODIES = ("run", "keep_newest", "drop_matching", "report", "on_host")


def _body(entry: Mapping[str, Any]) -> dict[str, Any]:
    """O corpo do passo, e ele é exatamente um.

    Nenhum corpo é um passo que não faz nada; dois corpos é um passo cuja ordem de
    execução ninguém escreveu. Os dois são erro de dado, e recusar aqui é mais
    barato do que descobrir em produção que um passo declarado nunca agiu.
    """
    present = sorted(name for name in BODIES if entry.get(name))
    if len(present) != 1:
        raise ValueError(
            f"o passo `{entry.get('name')}` precisa de exatamente um corpo entre "
            f"{', '.join(BODIES)}; veio {', '.join(present) or 'nenhum'}"
        )

    if present == ["on_host"]:
        return {"on_host": True}
    if present == ["run"]:
        return {"run": _argv(entry["run"])}
    if present == ["report"]:
        return {"report": _report(entry["report"])}
    if present == ["keep_newest"]:
        body = _object(entry["keep_newest"], dimension="keep_newest")
        _require(body, "root", dimension="keep_newest")
        return {"keep_newest": KeepNewest(root=expand(body["root"]), keep=int(body.get("keep", 1)))}
    body = _object(entry["drop_matching"], dimension="drop_matching")
    _require(body, "root", "suffix", dimension="drop_matching")
    return {"drop_matching": DropMatching(root=expand(body["root"]), suffix=body["suffix"])}


def _report(raw: Any) -> Report:
    body = _object(raw, dimension="report")
    _require(body, "command", "codes", dimension="report")
    return Report(command=_argv(body["command"]), codes=_codes(body["codes"]))


def _codes(raw: Any) -> Mapping[int, str]:
    """O mapa de código de saída para canal, e o que ele não aceita.

    O zero fica de fora por decisão, e não por descuido: ele é o silêncio de um
    passo saudável, e um canal amarrado a ele alarmaria toda vez que estivesse
    tudo bem -- que é o jeito mais rápido de treinar o operador a ignorar o canal.
    """
    entries = _object(raw, dimension="report.codes")
    codes: dict[int, str] = {}
    for key, alarm in entries.items():
        code = _exit_code(key)
        if code == 0:
            raise ValueError(
                "o código 0 de um corpo `report` não pode ser mapeado para canal nenhum: "
                "ele é o silêncio de um passo que rodou e não tinha nada a relatar"
            )
        codes[code] = str(alarm)
    if not codes:
        raise ValueError(
            "o corpo `report` precisa mapear pelo menos um código em `codes`; sem mapa, "
            "todo código diferente de zero viraria falha genérica e o corpo não teria razão "
            "de existir"
        )
    return codes


def _exit_code(key: Any) -> int:
    try:
        return int(key)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"chave de `report.codes` precisa ser um código de saída inteiro: veio {key!r}"
        ) from exc


def _argv(raw: Any) -> tuple[str, ...]:
    """O comando, com o executável expandido em caminho absoluto.

    O passo roda em **subprocesso não interativo**, disparado do agendador do host:
    ali não há arquivo de rc, e o PATH é o mínimo do sistema. `npm`, `pnpm` e `uv`
    moram em `~/.local/bin`, que não está nesse PATH. Um nome nu funcionaria no
    terminal e falharia na tarefa, que é exatamente a classe de erro que a issue
    #20 consertou ao exigir que todo nome seja alcançável pelo nome real.

    Só o executável é expandido: o resto do comando é argumento, e um argumento que
    começa com `~` é do comando, não deste dado.
    """
    parts = [str(part) for part in raw]
    if not parts:
        raise ValueError("corpo `run` vazio: um passo sem comando nunca age")
    return (expand(parts[0]), *parts[1:])


def _object(raw: Any, *, dimension: str) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"`{dimension}` precisa ser um objeto, veio {type(raw).__name__}")
    return raw


def _entries(raw: Any) -> Sequence[Mapping[str, Any]]:
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        raise ValueError(f"esperava uma lista de entradas, veio {type(raw).__name__}")
    entries: list[Mapping[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise ValueError(f"entrada de configuração precisa ser um objeto: {entry!r}")
        entries.append(entry)
    return entries


def load_desired(path: Path = DEFAULT_CONFIG_PATH) -> Desired:
    return Desired.from_dict(json.loads(path.read_text(encoding="utf-8")))
