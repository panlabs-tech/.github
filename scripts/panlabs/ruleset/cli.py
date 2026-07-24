"""A interface do script de ruleset.

Plano por default: rodar sem argumento nunca muda nada. Aplicar exige `--apply`,
explicito, e so contra a org viva -- aplicar a partir de um retrato salvo seria
agir sobre um estado que ja pode nao existir mais.

    uv run panlabs-ruleset                     # o plano da org viva
    uv run panlabs-ruleset --json              # o mesmo plano, serializado
    uv run panlabs-ruleset --observed f.json   # o plano de um retrato salvo
    uv run panlabs-ruleset --apply             # aplica
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from panlabs import gh
from panlabs.plan import Plan, apply
from panlabs.ruleset.applier import EFFECTS
from panlabs.ruleset.config import DEFAULT_CONFIG_PATH, Desired, load_desired
from panlabs.ruleset.model import Observed
from panlabs.ruleset.observe import build_observed, fetch_raw, observed_to_dict
from panlabs.ruleset.planner import plan

DEFAULT_ORG = "panlabs-tech"

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="panlabs-ruleset",
        description=(
            "Converge a protecao de branch da org para a configuracao desejada. "
            "Sem argumento, so mostra o plano."
        ),
    )
    parser.add_argument("--org", default=DEFAULT_ORG, help=f"org alvo (default: {DEFAULT_ORG})")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"configuracao desejada (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--observed",
        type=Path,
        help="le o estado observado deste arquivo em vez de consultar a org viva",
    )
    parser.add_argument(
        "--dump-observed",
        type=Path,
        metavar="PATH",
        help="grava o estado observado cru neste arquivo (util para virar fixture)",
    )
    parser.add_argument("--json", action="store_true", help="imprime o plano serializado")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="APLICA o plano. Sem esta flag nada e alterado.",
    )
    return parser


def _report_undecided(desired: Desired, config: Path) -> None:
    if desired.is_decided:
        return
    print(
        f"Configuracao desejada incompleta em {config}: "
        f"{', '.join(desired.undecided)} ainda sem decisao.\n"
        "Nada e planejado para uma dimensao nao decidida. Os valores sao da spec de Org #2.\n",
        file=sys.stderr,
    )


def _why_empty(the_plan: Plan, desired: Desired, config: Path) -> str:
    """Um plano vazio tem duas causas opostas, e confundi-las seria caro.

    Se a configuracao desejada ainda nao foi decidida, vazio significa "nada foi
    pedido" -- nao "esta tudo conforme". So quem carregou o dado sabe a diferenca.
    """
    if the_plan:
        return ""
    if desired.is_decided:
        return "O estado observado ja converge com o desejado."
    return (
        f"Isso NAO quer dizer que a frota esta conforme: {', '.join(desired.undecided)} "
        f"ainda nao foi decidido em {config}, entao nada foi pedido."
    )


def _summarize(observed: Observed) -> str:
    governed = sum(1 for repo in observed.repos if repo.rulesets_governing_default_branch())
    classic = sum(1 for repo in observed.repos if repo.classic_protection is not None)
    return (
        f"Org {observed.org}: {len(observed.repos)} repo(s) na org viva, "
        f"{governed} com ruleset na branch default, {classic} com protecao classica."
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.apply and args.observed:
        print(
            "--apply nao aceita --observed: aplicar a partir de um retrato salvo "
            "agiria sobre um estado que pode ja ter mudado.",
            file=sys.stderr,
        )
        return 2

    try:
        desired = load_desired(args.config)
        raw = (
            json.loads(args.observed.read_text(encoding="utf-8"))
            if args.observed
            else fetch_raw(args.org)
        )
    except (OSError, ValueError, gh.GhError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    observed = build_observed(raw)

    if args.dump_observed:
        args.dump_observed.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    _report_undecided(desired, args.config)
    the_plan = plan(observed, desired)

    if args.json:
        print(the_plan.to_json())
    else:
        print(_summarize(observed))
        print()
        print(json.dumps(observed_to_dict(observed), indent=2, ensure_ascii=False))
        print()
        print(the_plan.render())
        print(_why_empty(the_plan, desired, args.config))

    if not args.apply:
        return 0

    return _apply(the_plan)


def _apply(the_plan: Plan) -> int:
    if not the_plan:
        return 0
    print(f"\nAplicando {len(the_plan)} item(ns)...", file=sys.stderr)
    try:
        apply(the_plan, EFFECTS)
    except gh.GhError as exc:
        print(f"erro ao aplicar: {exc}", file=sys.stderr)
        return 1
    print("Aplicado. Rode de novo para conferir que o plano saiu vazio.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
