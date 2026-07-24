"""A interface do checker de conformidade.

Read-only por construção: não existe flag de aplicação, porque não existe
efeito que mute nada. "Aplicar" aqui é só formatar e notificar -- exatamente
o que este CLI faz. Nunca é chamado por workflow de PR nenhum: anatomia é
propriedade do repositório, não do diff.

    uv run panlabs-checker                     # a matriz da org viva
    uv run panlabs-checker --json              # a mesma matriz, serializada
    uv run panlabs-checker --observed f.json   # a matriz de um retrato salvo

O código de saída distingue os dois canais de alarme: 2 se algum repositório
falhou a observação (erro), 1 se a matriz tem deriva sem nenhum erro, 0 se
está limpa. Um token expirado não pode virar "toda a frota está fora do
padrão": por isso erro pesa mais que deriva, nunca o contrário.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from panlabs import gh
from panlabs.checker.observe import build_observed, fetch_raw
from panlabs.checker.planner import ERROR_VERDICT, plan
from panlabs.plan import Plan, dump_raw, load_raw

DEFAULT_ORG = "panlabs-tech"

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="panlabs-checker",
        description=(
            "Mede a frota contra a anatomia e emite a matriz repositório x item. "
            "Read-only: rodar isto nunca muda nada, em nenhum repo, em nenhum momento."
        ),
    )
    parser.add_argument("--org", default=DEFAULT_ORG, help=f"org alvo (default: {DEFAULT_ORG})")
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
    parser.add_argument("--json", action="store_true", help="imprime a matriz serializada")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        raw = load_raw(args.observed, lambda: fetch_raw(args.org))
    except (OSError, ValueError, gh.GhError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    observed = build_observed(raw)
    dump_raw(args.dump_observed, raw)

    the_matrix = plan(observed)

    if args.json:
        print(the_matrix.to_json())
    else:
        print(f"Org {observed.org}: {len(observed.repos)} repo(s) avaliado(s).\n")
        print(the_matrix.render())
        if not the_matrix:
            print("Nenhuma deriva ou erro no catálogo-semente avaliado.")

    return _exit_code(the_matrix)


def _exit_code(the_matrix: Plan) -> int:
    verdicts = {item.payload.get("verdict") for item in the_matrix}
    if ERROR_VERDICT in verdicts:
        return 2
    if verdicts:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
