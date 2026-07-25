"""A interface do script de máquina.

Plano por default: rodar sem argumento nunca muda nada, e é essa rodada que serve
de verificação de invariante. Aplicar exige `--apply`, explícito.

    uv run panlabs-machine                     # o plano da máquina viva
    uv run panlabs-machine --json              # o mesmo plano, serializado
    uv run panlabs-machine --observed f.json   # o plano de um retrato salvo
    uv run panlabs-machine --apply             # aplica o que é aplicável

Numa issue que apaga diretório de um giga e mexe na postura de permissão do
agente, plano por default deixa de ser conveniência e vira requisito de segurança.

Este script não toca a org e não pede token nenhum: o alvo dele é o global desta
máquina. A autorização de repositórios no gerenciador de runtime também não mora
aqui, porque ela falha sem terminal interativo e é ato do operador, uma vez só.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from panlabs.machine.applier import EFFECTS
from panlabs.machine.config import DEFAULT_CONFIG_PATH, load_desired
from panlabs.machine.model import Observed
from panlabs.machine.observe import (
    DEFAULT_AGENT_SETTINGS,
    DEFAULT_GLOBAL_SKILLS,
    DEFAULT_WORKSPACES,
    build_observed,
    fetch_raw,
    observed_to_dict,
)
from panlabs.machine.planner import plan
from panlabs.plan import Plan, apply, dump_raw, load_raw, report_undecided, why_empty

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="panlabs-machine",
        description=(
            "Converge o equipamento global desta máquina: os nomes que precisam ser "
            "alcançáveis em subprocesso, os diretórios aposentados, a negação de "
            "leitura sobre credencial e a cláusula de zero redundância das skills. "
            "Sem argumento, só mostra o plano."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"configuração desejada (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_AGENT_SETTINGS,
        help=f"configuração global do agente (default: {DEFAULT_AGENT_SETTINGS})",
    )
    parser.add_argument(
        "--global-skills",
        type=Path,
        action="append",
        metavar="PATH",
        help=(
            "raiz de skill global; repetível. Os dois diretórios que a CLI de "
            f"distribuição usa são o default: {', '.join(str(p) for p in DEFAULT_GLOBAL_SKILLS)}"
        ),
    )
    parser.add_argument(
        "--workspaces",
        type=Path,
        default=DEFAULT_WORKSPACES,
        help=f"raiz varrida por skill vendorizada (default: {DEFAULT_WORKSPACES})",
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
        help="APLICA o plano, menos os itens retidos. Sem esta flag nada é alterado.",
    )
    return parser


def _summarize(observed: Observed) -> str:
    unreachable = [link.name for link in observed.links if not link.present]
    still_there = sum(1 for entry in observed.retire if entry.present)
    weight = sum(entry.bytes for entry in observed.retire if entry.present)
    loaded = sum(1 for cred in observed.credentials if cred.present and cred.entries)
    return (
        f"Máquina: {len(observed.links) - len(unreachable)}/{len(observed.links)} nome(s) "
        f"alcançável(is) pelo nome real"
        + (f" (faltam: {', '.join(unreachable)})" if unreachable else "")
        + f".\n{still_there} diretório(s) aposentado(s) ainda no disco, "
        f"{weight / 1_000_000_000:.2f} GB.\n"
        f"{loaded} lugar(es) de credencial com conteúdo hoje: é esse o raio real.\n"
        f"{len(observed.global_skills)} skill(s) no global, "
        f"{len(observed.vendored_skills)} cópia(s) dentro de repositório."
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.apply and args.observed:
        print(
            "--apply não aceita --observed: aplicar a partir de um retrato salvo "
            "agiria sobre um estado que pode já ter mudado, e aqui isso apagaria "
            "diretório.",
            file=sys.stderr,
        )
        return 2

    try:
        desired = load_desired(args.config)
        raw = load_raw(
            args.observed,
            lambda: fetch_raw(
                desired,
                settings=args.settings,
                global_skills=tuple(args.global_skills or DEFAULT_GLOBAL_SKILLS),
                workspaces=args.workspaces,
            ),
        )
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
        print(_summarize(observed))
        print()
        if args.show_observed:
            print(json.dumps(observed_to_dict(observed), indent=2, ensure_ascii=False))
            print()
        print(the_plan.render())
        print(why_empty(the_plan, desired.undecided, args.config, subject="a máquina"))

    if not args.apply:
        return 0

    return _apply(the_plan)


def _apply(the_plan: Plan) -> int:
    if the_plan.held:
        print(
            f"\n{len(the_plan.held)} item(ns) do plano estão retidos e continuam com você:",
            file=sys.stderr,
        )
        for item in the_plan.held:
            print(f"  {item.action}  {item.target}: {item.hold}", file=sys.stderr)

    if not the_plan.applicable:
        return 0

    print(f"\nAplicando {len(the_plan.applicable)} item(ns)...", file=sys.stderr)
    try:
        apply(the_plan, EFFECTS)
    except OSError as exc:
        print(f"erro ao aplicar: {exc}", file=sys.stderr)
        return 1
    print("Aplicado. Rode de novo para conferir que o plano saiu vazio.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
