"""Os efeitos do espaço de trabalho: um ato por ação, e nenhuma decisão.

Cada efeito recebe um item cujo `payload` o planner já montou por inteiro: o
endereço final de uma movimentação, o refspec exato de um push, a mensagem do
commit de preservação. Nada disso é recalculado aqui.

Duas escolhas de ato merecem registro, porque parecem detalhe e não são:

- o commit de preservação passa por cima dos ganchos locais. Um linter reprovando
  o commit deixaria o trabalho exatamente onde ele estava, que é o único desfecho
  que esta issue não pode ter.
- reparar o vínculo de um worktree é `git worktree repair`, e não escrita de
  arquivo. O ponteiro é dos dois lados, e o próprio git é quem sabe os dois.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from panlabs.plan import Effect, PlanItem
from panlabs.workspace.planner import (
    CLONE_REPO,
    COMMIT_LOCAL,
    DISCARD_DIR,
    DISCARD_WORKTREE,
    DROP_STASH,
    MOVE_REPO,
    MOVE_WORKTREE,
    PRESERVE_STASH,
    PUSH_BRANCH,
    REPAIR_WORKTREE,
    REWRITE_REMOTE,
)

__all__ = ["GitError", "build_effects"]


class GitError(RuntimeError):
    """Um comando de git falhou. Falha aqui é erro, e não estado a interpretar."""


def _git(cwd: Path, *args: str) -> None:
    """Roda o git e estoura na falha.

    Ao contrário do observador, que lê estados normais e trata erro como ausência,
    aqui qualquer falha é falha: o item já foi decidido e revisado, e engoli-la
    faria o script relatar convergência sobre um ato que não aconteceu.
    """
    done = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip()
        raise GitError(f"`git {' '.join(args)}` em {cwd} falhou: {detail}")


def build_effects() -> dict[str, Effect]:
    """A tabela de despacho. Sem ramificação de decisão, e não pode haver."""

    def clone_repo(item: PlanItem) -> None:
        dest = Path(item.target)
        dest.parent.mkdir(parents=True, exist_ok=True)
        _git(dest.parent, "clone", str(item.payload["url"]), dest.name)

    def rewrite_remote(item: PlanItem) -> None:
        _git(Path(item.target), "remote", "set-url", "origin", str(item.payload["url"]))

    def commit_local(item: PlanItem) -> None:
        """Commita exatamente os arquivos que o item mostrou, e nada além deles.

        `git add -A` sem caminho pegaria também o que apareceu entre o plano e a
        aplicação, e o ato deixaria de ser o que o operador revisou. Com os
        caminhos, o `-A` continua servindo para o que importa: um arquivo daquela
        lista que sumiu no meio entra como remoção em vez de estourar.
        """
        here = Path(item.target)
        files = [str(name) for name in item.payload["files"]]
        _git(here, "add", "-A", "--", *files)
        _git(here, "commit", "--no-verify", "-m", str(item.payload["message"]))

    def push_branch(item: PlanItem) -> None:
        _git(Path(item.target), "push", "origin", str(item.payload["refspec"]))

    def preserve_stash(item: PlanItem) -> None:
        here = Path(item.target)
        branch = str(item.payload["branch"])
        _git(here, "branch", branch, str(item.payload["sha"]))
        _git(here, "push", "origin", f"{branch}:refs/heads/{branch}")

    def drop_stash(item: PlanItem) -> None:
        _git(Path(item.target), "stash", "drop", str(item.payload["ref"]))

    def move_dir(item: PlanItem) -> None:
        destination = Path(str(item.payload["to"]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(item.target, destination)

    def repair_worktree_link(item: PlanItem) -> None:
        _git(Path(str(item.payload["parent"])), "worktree", "repair", str(item.payload["worktree"]))

    def discard_dir(item: PlanItem) -> None:
        shutil.rmtree(str(item.payload["path"]), ignore_errors=False)

    def discard_worktree(item: PlanItem) -> None:
        parent = Path(str(item.payload["parent"]))
        _git(parent, "worktree", "remove", "--force", str(item.payload["path"]))

    return {
        CLONE_REPO: clone_repo,
        REWRITE_REMOTE: rewrite_remote,
        COMMIT_LOCAL: commit_local,
        PUSH_BRANCH: push_branch,
        PRESERVE_STASH: preserve_stash,
        DROP_STASH: drop_stash,
        MOVE_REPO: move_dir,
        MOVE_WORKTREE: move_dir,
        REPAIR_WORKTREE: repair_worktree_link,
        DISCARD_DIR: discard_dir,
        DISCARD_WORKTREE: discard_worktree,
    }
