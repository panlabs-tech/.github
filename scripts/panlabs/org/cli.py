"""A interface do script de org e repo.

Plano por default: rodar sem argumento nunca muda nada, e é essa rodada que
serve de **verificação de invariante**. Aplicar exige `--apply`, explícito, e só
contra a org viva: aplicar a partir de um retrato salvo seria agir sobre um
estado que já pode não existir mais.

    uv run panlabs-org                     # o plano da org viva
    uv run panlabs-org --json              # o mesmo plano, serializado
    uv run panlabs-org --observed f.json   # o plano de um retrato salvo
    uv run panlabs-org --apply             # aplica o que é aplicável

Ler e aplicar exigem token com escopo `admin:org`, e o comando diz isso **antes**
de tocar a rede: descobrir no meio da execução que falta escopo é o pior momento
possível. Elevar o token é ato do operador, nunca do agente.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from panlabs import gh
from panlabs.org.applier import EFFECTS
from panlabs.org.config import DEFAULT_CONFIG_PATH, load_desired
from panlabs.org.model import Observed
from panlabs.org.observe import build_observed, fetch_raw, observed_to_dict
from panlabs.org.planner import MANUAL_ACTIONS, plan
from panlabs.plan import Plan, PlanItem, apply, dump_raw, load_raw, report_undecided, why_empty

DEFAULT_ORG = "panlabs-tech"

ADMIN_SCOPE_NOTICE = (
    "Esta configuração exige token com escopo `admin:org`, tanto para ler as "
    "dimensões de segurança quanto para aplicar qualquer uma delas.\n"
    "Se a chamada seguinte falhar com 403, eleve o token com "
    "`gh auth refresh -h github.com -s admin:org` e rode de novo.\n"
    "Elevar o escopo é ato do operador, não do agente.\n"
)

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="panlabs-org",
        description=(
            "Converge a configuração de org e de repositório que não é ruleset: a "
            "política de Actions que sustenta a esteira, as features de segurança, a "
            "vitrine e as features desligadas. Sem argumento, só mostra o plano."
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
    parser.add_argument("--json", action="store_true", help="imprime o plano serializado")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="APLICA o plano, menos os itens que só existem na web. Sem esta flag nada é alterado.",
    )
    return parser


def _summarize(observed: Observed) -> str:
    org = observed.org
    esteira = "ligada" if org.actions.can_approve_pull_requests else "DESLIGADA"
    protegidos = sum(1 for repo in observed.repos if repo.secret_scanning and repo.push_protection)
    return (
        f"Org {org.login}: {len(observed.repos)} repo(s) na org viva, "
        f"{protegidos} com secret scanning e push protection, "
        f"{len(org.pinned_repos)} pin(s) no perfil.\n"
        f"Política de Actions que cria e aprova PR (a esteira): {esteira}."
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

    if args.observed is None:
        print(ADMIN_SCOPE_NOTICE, file=sys.stderr)

    try:
        desired = load_desired(args.config)
        raw = load_raw(args.observed, lambda: fetch_raw(args.org))
        observed = build_observed(raw)
    except (OSError, ValueError, gh.GhError) as exc:
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
        print(why_empty(the_plan, desired.undecided, args.config, subject="a org"))

    if not args.apply:
        return 0

    return _apply(the_plan)


def _apply(the_plan: Plan) -> int:
    """Aplica o que tem efeito, e devolve o resto ao operador em vez de fingir.

    A separação é do plano, não do applier: uma ação manual simplesmente não tem
    efeito registrado, e o `apply` do seam continua sendo uma tabela de despacho
    sem decisão nenhuma.
    """
    appliable: list[PlanItem] = []
    manual: list[PlanItem] = []
    for item in the_plan:
        (manual if item.action in MANUAL_ACTIONS else appliable).append(item)

    if manual:
        print(
            f"\n{len(manual)} item(ns) do plano não têm chamada de API que os aplique, "
            "e continuam com você:",
            file=sys.stderr,
        )
        for item in manual:
            print(f"  {item.action}  {item.target}: {item.reason}", file=sys.stderr)

    if not appliable:
        return 0

    print(f"\nAplicando {len(appliable)} item(ns)...", file=sys.stderr)
    try:
        apply(Plan(tuple(appliable)), EFFECTS)
    except gh.GhError as exc:
        print(f"erro ao aplicar: {exc}", file=sys.stderr)
        return 1
    print("Aplicado. Rode de novo para conferir que o plano saiu vazio.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
