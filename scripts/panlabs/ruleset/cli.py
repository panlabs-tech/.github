"""A interface do script de ruleset.

Plano por default: rodar sem argumento nunca muda nada. Aplicar exige `--apply`,
explícito, e só contra a org viva: aplicar a partir de um retrato salvo seria
agir sobre um estado que já pode não existir mais.

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
from panlabs.plan import Plan, apply, dump_raw, load_raw, report_undecided, why_empty
from panlabs.ruleset.applier import EFFECTS
from panlabs.ruleset.config import DEFAULT_CONFIG_PATH, load_desired
from panlabs.ruleset.model import Observed, RepoState
from panlabs.ruleset.observe import build_observed, fetch_raw, observed_to_dict
from panlabs.ruleset.planner import plan

DEFAULT_ORG = "panlabs-tech"

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="panlabs-ruleset",
        description=(
            "Converge a proteção de branch da org para a configuração desejada. "
            "Sem argumento, só mostra o plano."
        ),
    )
    parser.add_argument("--org", default=DEFAULT_ORG, help=f"org alvo (default: {DEFAULT_ORG})")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"configuração desejada (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--observed",
        type=Path,
        help="lê o estado observado deste arquivo em vez de consultar a org viva",
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
    parser.add_argument(
        "--only",
        action="append",
        metavar="ORG/REPO",
        help=(
            "restringe o plano a este repo (repetível) e afirma que a CI dele já "
            "publica os nomes fixos de check, levantando o portão que retém os "
            "repos ainda não retrofitados. Sem esta flag, o plano cobre a org "
            "inteira e aplica só a quem já fala o contrato."
        ),
    )
    parser.add_argument("--json", action="store_true", help="imprime o plano serializado")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="APLICA o plano. Sem esta flag nada é alterado.",
    )
    return parser


def _restrict(observed: Observed, only: list[str]) -> tuple[Observed, tuple[RepoState, ...]]:
    """Recorta o observado para os repos nomeados, e devolve quem ficou de fora.

    O recorte acontece aqui, não no planner: o planner continua enxergando a
    org inteira que lhe é dada, e `--only` é decisão de invocação, não de
    anatomia. Quem ficou de fora não desaparece silenciosamente -- vira o
    registro que `_report_only` imprime.
    """
    keep = set(only)
    kept = tuple(repo for repo in observed.repos if repo.name in keep)
    excluded = tuple(repo for repo in observed.sorted_repos() if repo.name not in keep)
    return Observed(org=observed.org, repos=kept), excluded


def _report_only(excluded: tuple[RepoState, ...]) -> None:
    """Quem ficou de fora do recorte, e não da aplicação.

    São coisas diferentes desde que o portão existe: sem `--only`, um repo não
    retrofitado continua no plano, retido e com o motivo à vista. Aqui ele nem
    foi olhado, e dizer o contrário faria o operador ler uma varredura da org
    onde houve um recorte.
    """
    if not excluded:
        return
    names = ", ".join(repo.name for repo in excluded)
    print(
        f"--only restringe o plano; {len(excluded)} repo(s) da org nem entram nesta "
        f"leitura, e portanto não são avaliados: {names}.",
        file=sys.stderr,
    )


def _summarize(observed: Observed) -> str:
    governed = sum(1 for repo in observed.repos if repo.rulesets_governing_default_branch())
    classic = sum(1 for repo in observed.repos if repo.classic_protection is not None)
    return (
        f"Org {observed.org}: {len(observed.repos)} repo(s) na org viva, "
        f"{governed} com ruleset na branch default, {classic} com proteção clássica."
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.apply and args.observed:
        print(
            "--apply não aceita --observed: aplicar a partir de um retrato salvo "
            "agiria sobre um estado que pode já ter mudado.",
            file=sys.stderr,
        )
        return 2

    try:
        desired = load_desired(args.config)
        raw = load_raw(args.observed, lambda: fetch_raw(args.org))
    except (OSError, ValueError, gh.GhError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    observed = build_observed(raw)
    dump_raw(args.dump_observed, raw)

    if args.only:
        unknown = sorted(set(args.only) - {repo.name for repo in observed.repos})
        if unknown:
            # Um nome errado sairia como plano vazio, que se lê como "já converge".
            print(
                f"--only nomeia repo(s) que não estão na org observada: {', '.join(unknown)}.",
                file=sys.stderr,
            )
            return 1
        observed, excluded = _restrict(observed, args.only)
        _report_only(excluded)

    report_undecided(desired.undecided, args.config)
    the_plan = plan(observed, desired, retrofitted=args.only or ())

    if args.json:
        print(the_plan.to_json())
    else:
        print(_summarize(observed))
        print()
        if args.show_observed:
            print(json.dumps(observed_to_dict(observed), indent=2, ensure_ascii=False))
            print()
        print(the_plan.render())
        print(why_empty(the_plan, desired.undecided, args.config, subject="a frota"))

    if not args.apply:
        return 0

    return _apply(the_plan)


def _apply(the_plan: Plan) -> int:
    if not the_plan.applicable:
        if the_plan.held:
            print(
                f"\nNada a aplicar: os {len(the_plan.held)} item(ns) do plano estão retidos, "
                "aguardando o retrofit de CI dos repos que eles tocam.",
                file=sys.stderr,
            )
        return 0

    withheld = f", {len(the_plan.held)} retido(s) de fora" if the_plan.held else ""
    print(f"\nAplicando {len(the_plan.applicable)} item(ns){withheld}...", file=sys.stderr)
    try:
        apply(the_plan, EFFECTS)
    except gh.GhError as exc:
        print(f"erro ao aplicar: {exc}", file=sys.stderr)
        return 1
    print("Aplicado. Rode de novo para conferir que o plano saiu vazio.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
