"""A interface do script de espaço de trabalho.

Plano por default: rodar sem argumento nunca muda nada, e é essa rodada que serve
de verificação do estado estacionário. Aplicar exige `--apply`, explícito.

    uv run panlabs-workspace                     # o plano do espaço vivo
    uv run panlabs-workspace --json              # o mesmo plano, serializado
    uv run panlabs-workspace --observed f.json   # o plano de um retrato salvo
    uv run panlabs-workspace --apply             # aplica o que é aplicável
    uv run panlabs-workspace --discard PATH --apply   # autoriza um alvo de descarte

Numa issue que apaga diretórios e reescreve remotes, plano por default deixa de
ser conveniência e vira requisito de segurança.

**Nenhum descarte é aplicável sem `--discard` nomeando o alvo.** Elegibilidade é
sugestão do critério; a decisão de apagar continua humana, alvo por alvo. Sem a
flag, os itens de descarte aparecem no plano, retidos e com o motivo à vista, e o
`apply` não encosta neles.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from panlabs import gh
from panlabs.plan import Plan, PlanItem, apply, dump_raw, load_raw, report_undecided, why_empty
from panlabs.workspace.applier import GitError, build_effects
from panlabs.workspace.config import DEFAULT_CONFIG_PATH, Desired, load_desired
from panlabs.workspace.model import EMPTY, REPO, WORKTREE, Observed
from panlabs.workspace.observe import build_observed, fetch_raw, observed_to_dict
from panlabs.workspace.planner import DISCARD_DIR, DISCARD_WORKTREE, plan

DEFAULT_ORG = "panlabs-tech"

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="panlabs-workspace",
        description=(
            "Converge o espaço de trabalho para o estado estacionário declarado: todo "
            "repo da org clonado sob o diretório da org, com o remote canônico; o que "
            "só existe local commitado e pushado; o que não é da org e já está em outro "
            "lugar, sugerido para descarte. Sem argumento, só mostra o plano."
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
        help="lê o estado observado deste arquivo em vez de olhar o espaço vivo",
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
        "--discard",
        action="append",
        metavar="PATH",
        help=(
            "autoriza o descarte deste alvo (repetível). É a aprovação humana, alvo "
            "por alvo, sem a qual nenhum diretório é apagado. O caminho é o que o "
            "plano mostra, que é o endereço **final**: um worktree de um repositório "
            "que se move é autorizado pelo endereço para onde ele vai. Um caminho que "
            "não é elegível é erro, e não silêncio."
        ),
    )
    parser.add_argument(
        "--only",
        action="append",
        metavar="PATH",
        help=(
            "restringe o plano a este caminho e ao que mora sob ele (repetível). O "
            "espaço de trabalho é da máquina inteira, e nem todo alvo dela está pronto "
            "para receber a convergência na mesma hora: uma árvore de trabalho com "
            "sessão viva em cima, por exemplo, teria o trabalho em voo commitado no "
            "meio. Sem a flag, o plano cobre o espaço inteiro."
        ),
    )
    parser.add_argument("--json", action="store_true", help="imprime o plano serializado")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="APLICA o plano, menos os itens retidos. Sem esta flag nada é alterado.",
    )
    return parser


def _summarize(observed: Observed) -> str:
    repos = [entry for entry in observed.dirs if entry.kind == REPO]
    worktrees = [entry for entry in observed.dirs if entry.kind == WORKTREE]
    empties = [entry for entry in observed.dirs if entry.kind == EMPTY]
    carrying = [entry for entry in observed.dirs if entry.only_local]
    return (
        f"Espaço de trabalho {observed.root}: {len(observed.dirs)} diretório(s), "
        f"{len(repos)} repositório(s), {len(worktrees)} worktree(s), {len(empties)} vazio(s).\n"
        f"Org {observed.org}: {len(observed.org_repos)} repo(s) na listagem viva.\n"
        f"{len(carrying)} diretório(s) carregam algo que só existe neste disco."
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
        raw = load_raw(args.observed, lambda: _fetch(args.org, desired))
        observed = build_observed(raw)
    except (OSError, ValueError, gh.GhError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    dump_raw(args.dump_observed, raw)
    report_undecided(desired.undecided, args.config, spec="spec de Máquina #3")

    the_plan = plan(observed, desired, approved=args.discard or ())
    if args.discard and (unknown := _unknown_targets(the_plan, args.discard)):
        # Um caminho errado sairia como plano sem aquele descarte, que se lê como
        # "aquele alvo não era elegível" quando na verdade foi erro de digitação.
        print(
            f"--discard nomeia alvo(s) que o critério não considera elegível(is): "
            f"{', '.join(unknown)}.",
            file=sys.stderr,
        )
        return 1

    if args.only:
        the_plan, left_out = _restrict(the_plan, args.only)
        _report_only(left_out)

    if args.json:
        print(the_plan.to_json())
    else:
        print(_summarize(observed))
        print()
        if args.show_observed:
            print(json.dumps(observed_to_dict(observed), indent=2, ensure_ascii=False))
            print()
        print(the_plan.render())
        print(why_empty(the_plan, desired.undecided, args.config, subject="o espaço de trabalho"))

    if not args.apply:
        return 0

    return _apply(the_plan)


def _fetch(org: str, desired: Desired) -> dict[str, object]:
    """Sem raiz decidida não há onde olhar, e olhar em outro lugar seria inventar."""
    if desired.root is None:
        return {"org": org, "root": "", "org_repos": [], "dirs": []}
    return fetch_raw(org, root=Path(desired.root))


def _restrict(the_plan: Plan, only: list[str]) -> tuple[Plan, int]:
    """Recorta o plano aos alvos pedidos, e diz quantos itens ficaram de fora.

    O recorte é do **plano**, e não do observado. Recortar o observado produziria
    um plano diferente, e errado: um worktree sem o pai à vista perderia a
    movimentação do pai que muda o endereço dele, e um repo da org escondido da
    listagem viraria clone duplicado. Aqui o planner continua enxergando o espaço
    inteiro, e `--only` é decisão de invocação.

    O casamento é por prefixo de caminho porque os alvos são caminhos, e o que se
    quer restringir é sempre uma subárvore: um repositório vem com os worktrees
    dele, que é a unidade em que a convergência faz sentido.
    """
    kept = tuple(item for item in the_plan if _touches(item, only))
    return Plan(items=kept), len(the_plan) - len(kept)


def _touches(item: PlanItem, roots: list[str]) -> bool:
    """Um item é do recorte quando **qualquer endereço que ele nomeia** está lá dentro.

    O alvo sozinho não basta, e o caso que prova isso é o worktree solto de um
    repositório que se move: ele não mora sob o pai em endereço nenhum, nem no de
    antes nem no de depois, porque a relação entre os dois é de parentesco e não de
    contenção. Casar só pelo alvo levaria a movimentação do pai e deixaria para
    trás o reparo do vínculo, que a spec chama de passo obrigatório, e o worktree
    que o recorte nem mencionou pararia de funcionar em silêncio.

    Varrer o payload inteiro é seguro porque o casamento é por caminho: um valor
    que não é endereço, como um remote ou um refspec, nunca fica sob a raiz do
    recorte.
    """
    named = [item.target, *(value for value in item.payload.values() if isinstance(value, str))]
    return any(_under_any(address, roots) for address in named)


def _under_any(target: str, roots: list[str]) -> bool:
    return any(target == root or target.startswith(f"{root.rstrip('/')}/") for root in roots)


def _report_only(left_out: int) -> None:
    """Quem ficou de fora não some em silêncio: um plano recortado não é o do espaço."""
    if not left_out:
        return
    print(
        f"--only recorta o plano; {left_out} item(ns) do espaço de trabalho estão fora "
        "desta leitura e continuam pendentes.",
        file=sys.stderr,
    )


def _unknown_targets(the_plan: Plan, discard: list[str]) -> list[str]:
    eligible = {item.target for item in the_plan if item.action in (DISCARD_DIR, DISCARD_WORKTREE)}
    return sorted(set(discard) - eligible)


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
        apply(the_plan, build_effects())
    except (OSError, GitError) as exc:
        print(f"erro ao aplicar: {exc}", file=sys.stderr)
        return 1
    print("Aplicado. Rode de novo para conferir que o plano saiu vazio.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
