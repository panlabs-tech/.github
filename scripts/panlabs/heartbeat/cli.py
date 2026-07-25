"""A interface do heartbeat.

Plano por default: rodar sem argumento nunca muda nada, e é essa rodada que serve
de verificação de invariante. Aplicar exige `--apply`, explícito.

    uv run panlabs-heartbeat                     # o plano desta máquina agora
    uv run panlabs-heartbeat --json              # o mesmo plano, serializado
    uv run panlabs-heartbeat --observed f.json   # o plano de um retrato salvo
    uv run panlabs-heartbeat --apply             # roda os passos que venceram

Quem chama isto de verdade é a tarefa do agendador do host, uma vez por dia, e ela
só entra no WSL quando já o encontrou de pé. O disparo é diário; a cadência de cada
passo é dele, e é o planner que a respeita.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from panlabs.heartbeat.applier import build_runner, write_standing_order
from panlabs.heartbeat.config import DEFAULT_CONFIG_PATH, Desired, load_desired
from panlabs.heartbeat.model import Observed
from panlabs.heartbeat.observe import (
    DEFAULT_STATE_DIR,
    build_observed,
    fetch_raw,
    observed_to_dict,
)
from panlabs.heartbeat.planner import plan, standing_order
from panlabs.plan import Plan, apply, dump_raw, load_raw, report_undecided, why_empty

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="panlabs-heartbeat",
        description=(
            "O heartbeat da máquina: hospedeiro de passos plugáveis. Cada passo "
            "declara em qual ramo roda (WSL de pé ou parado), qual é a cadência "
            "dele e qual canal de alarme ele usa. Sem argumento, só mostra o plano."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"configuração desejada (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_DIR,
        help=(
            "diretório de marcas, alarmes e log; ele aponta para o lado do host, "
            f"que é o único que o enxerga com o WSL parado (default: {DEFAULT_STATE_DIR})"
        ),
    )
    parser.add_argument(
        "--observed",
        type=Path,
        help="lê o estado observado deste arquivo em vez de olhar a máquina viva",
    )
    parser.add_argument(
        "--dump-observed",
        type=Path,
        metavar="PATH",
        help="grava o estado observado cru neste arquivo (útil para virar fixture)",
    )
    parser.add_argument(
        "--show-observed",
        action="store_true",
        help="imprime o estado observado antes do plano",
    )
    parser.add_argument("--json", action="store_true", help="imprime o plano serializado")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="RODA os passos do plano. Sem esta flag nada é alterado.",
    )
    return parser


def _summarize(observed: Observed, desired: Desired) -> str:
    branch = observed.branch or "não consultado"
    disk = (
        f"{observed.host.free_bytes / 1_000_000_000:.1f} GB livres no host"
        if observed.host.measured
        else "disco do host NÃO medido: essa métrica não existe de dentro do WSL"
    )
    ran = "nunca" if observed.last_run is None else observed.last_run.isoformat(timespec="minutes")
    return (
        f"Ramo: {branch}. {disk}.\n"
        f"Última execução: {ran}.\n"
        f"{len(desired.steps or ())} passo(s) declarado(s), "
        f"{len(desired.channels or ())} canal(is) de alarme."
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.apply and args.observed:
        print(
            "--apply não aceita --observed: um retrato salvo pode dizer que o WSL "
            "está parado quando ele está de pé, e compactar um disco vivo é o único "
            "desastre que este desenho tem como causar.",
            file=sys.stderr,
        )
        return 2

    try:
        desired = load_desired(args.config)
        raw = load_raw(args.observed, lambda: fetch_raw(desired, state_dir=args.state))
        observed = build_observed(raw)
    except (OSError, ValueError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    dump_raw(args.dump_observed, raw)

    report_undecided(desired.undecided, args.config)
    the_plan = plan(observed, desired)

    if args.json:
        print(the_plan.to_json())
    else:
        print(_summarize(observed, desired))
        print()
        if args.show_observed:
            print(json.dumps(observed_to_dict(observed), indent=2, ensure_ascii=False))
            print()
        print(the_plan.render())
        print(why_empty(the_plan, desired.undecided, args.config, subject="a máquina"))

    if not args.apply:
        return 0

    return _apply(the_plan, observed, desired, args.state)


def _apply(the_plan: Plan, observed: Observed, desired: Desired, state: Path) -> int:
    runner = build_runner(state_dir=state, now=observed.now)
    try:
        apply(the_plan, runner.effects)
        write_standing_order(standing_order(observed, desired), state)
        runner.commit()
    except OSError as exc:
        print(f"erro ao aplicar: {exc}", file=sys.stderr)
        return 1

    for alarm in runner.alarms:
        print(f"alarme[{alarm.alarm}] {alarm.message}", file=sys.stderr)

    if not runner.failed:
        return 0
    print(
        f"\n{len(runner.failed)} passo(s) falharam: {', '.join(runner.failed)}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
