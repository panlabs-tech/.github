"""A fronteira com o espaço de trabalho vivo: lê o disco e o git, decide nada.

Duas medições aqui existem porque o **default do git mente**, e mente em direções
opostas:

- `git status` colapsa diretório não rastreado num item só e **subconta** o que se
  perderia. Por isso a leitura é sempre com todos os arquivos expandidos.
- comparar branch com remote por identificador **superconta** sob squash-merge, e
  foi assim que uma varredura anterior gerou alarme falso de 30 commits em 22
  branches supostamente ausentes de todo remote. Por isso o que se compara aqui é
  **árvore de conteúdo**, e o identificador é medido em separado, para o plano
  poder dizer que não o usou.

O que o git já ignora nunca é lido, e essa é a cláusula que faz o eixo terminar em
vez de virar arqueologia infinita.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from panlabs import gh
from panlabs.workspace.model import (
    EMPTY,
    PLAIN,
    REPO,
    WORKTREE,
    Branch,
    Observed,
    Stash,
    WorkDir,
)

__all__ = [
    "DEFAULT_ROOT",
    "HISTORY_DEPTH",
    "build_observed",
    "fetch_raw",
    "observed_to_dict",
    "scan",
]

DEFAULT_ROOT = Path.home() / "workspaces"

HISTORY_DEPTH = 20_000
"""Quantos commits de remote entram na comparação de conteúdo.

Um limite honesto e declarado: a varredura é por árvore, e uma branch que
aterrissou há mais de vinte mil commits aparece como não pushada, o que erra para
o lado de preservar. Sem limite, um repositório grande faria a leitura arrastar.
"""


def _git(cwd: Path, *args: str) -> str:
    """Roda o git e devolve a saída. Falha vira vazio: aqui só se observa.

    Um repositório sem remote, sem stash ou sem branch responde com erro a várias
    destas perguntas, e nenhum desses casos é excepcional: são estados normais que
    o planner precisa enxergar como ausência.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return done.stdout if done.returncode == 0 else ""


def fetch_raw(org: str, *, root: Path = DEFAULT_ROOT) -> dict[str, Any]:
    """O retrato cru do espaço de trabalho, no formato que `build_observed` lê."""
    dirs = scan(root, org)
    return {
        "org": org,
        "root": str(root),
        "org_repos": list(gh.repo_names(org)),
        "dirs": [dirs[key] for key in sorted(dirs)],
    }


def scan(root: Path, org: str) -> dict[str, dict[str, Any]]:
    """A metade de disco da observação, sem tocar a rede.

    Separada da metade de org porque as duas falham de jeitos diferentes e uma
    delas nem sempre está disponível: o disco responde sempre, a listagem da org
    depende de credencial. Ler o espaço de trabalho não deveria exigir rede.
    """
    dirs: dict[str, dict[str, Any]] = {}
    for path in _candidates(root, org):
        entry = _look_at(path)
        dirs[entry["path"]] = entry

    for entry in list(dirs.values()):
        if entry["kind"] != REPO:
            continue
        repo = Path(entry["path"])
        hanging = _worktree_paths(repo)
        entry["dirty"] = _without_worktrees(entry.get("dirty") or [], repo, hanging)
        for found in hanging:
            if root in found.parents:
                dirs.setdefault(str(found), _look_at(found))
    return dirs


def _candidates(root: Path, org: str) -> Iterator[Path]:
    """Os diretórios do espaço de trabalho, com os da org um nível mais fundo.

    O diretório que espelha a org não é candidato a nada: ele é o agrupador, e
    tratá-lo como diretório comum o poria na conta da faxina. Os filhos dele é que
    são repositórios.

    `iterdir` não filtra oculto de propósito. O repo meta da org tem nome começando
    por ponto, e um glob ingênuo o perderia para sempre.
    """
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir()):
        if entry.is_symlink() or not entry.is_dir():
            continue
        if entry.name == org:
            yield from (child for child in sorted(entry.iterdir()) if child.is_dir())
            continue
        yield entry


def _look_at(path: Path) -> dict[str, Any]:
    """O que este diretório é, e o que ele carrega que só existe aqui."""
    dot_git = path / ".git"
    if not dot_git.exists():
        kind = EMPTY if not any(path.iterdir()) else PLAIN
        return {"path": str(path), "kind": kind}

    common = _common_dir(path)
    parent = str(common.parent) if common.name == ".git" else ""
    kind = WORKTREE if dot_git.is_file() else REPO

    entry: dict[str, Any] = {
        "path": str(path),
        "kind": kind,
        "remote": _git(path, "remote", "get-url", "origin").strip(),
        "parent": parent if kind == WORKTREE else "",
        "head": _git(path, "symbolic-ref", "--short", "-q", "HEAD").strip(),
        "dirty": _dirty(path),
        "branches": _branches(path, kind),
    }
    if kind == REPO:
        entry["stashes"] = _stashes(path)
    return entry


def _common_dir(path: Path) -> Path:
    """O `.git` compartilhado: é ele que diz quem é o pai de um worktree."""
    found = _git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    return Path(found) if found else path / ".git"


def _dirty(path: Path) -> list[str]:
    """Todo arquivo que só existe neste disco, um por um.

    `--untracked-files=all` é o ponto: o default colapsa um diretório não rastreado
    num item só, e um plano que dissesse "1 item" onde há dezenas de arquivos
    subcontaria exatamente o que se perderia ao apagar o diretório.

    Sem `--ignored`, também de propósito: o que o git já ignora não é protegido.
    """
    out = _git(path, "-c", "core.quotePath=false", "status", "--porcelain=v1", "-uall", "-z")
    files: list[str] = []
    chunks = [chunk for chunk in out.split("\0") if chunk]
    index = 0
    while index < len(chunks):
        entry = chunks[index]
        index += 1
        if len(entry) < 4:
            continue
        code, name = entry[:2], entry[3:]
        if code[0] in ("R", "C"):
            # Renomeado e copiado gastam duas entradas: a nova e a de origem.
            index += 1
        files.append(name)
    return sorted(files)


def _branches(path: Path, kind: str) -> list[dict[str, Any]]:
    """As branches locais, com conteúdo e identificador medidos em separado.

    Um worktree reporta só a branch que ele carrega; as outras são do pai, e
    contá-las duas vezes faria o mesmo push aparecer duas vezes no plano.
    """
    listing = _git(
        path, "for-each-ref", "--format=%(refname:short)\t%(objectname)\t%(tree)", "refs/heads"
    )
    rows = [line.split("\t") for line in listing.splitlines() if line.count("\t") == 2]
    if kind == WORKTREE:
        head = _git(path, "symbolic-ref", "--short", "-q", "HEAD").strip()
        rows = [row for row in rows if row[0] == head]

    commits, trees = _remote_reach(path)
    return [
        {
            "name": name,
            "content_on_remote": tree in trees,
            "commit_on_remote": sha in commits,
        }
        for name, sha, tree in rows
    ]


def _remote_reach(path: Path) -> tuple[set[str], set[str]]:
    """O que os remotes alcançam: os identificadores, e as **árvores**.

    São dois conjuntos porque são duas perguntas, e só a segunda decide. Sob
    squash-merge o commit que aterrissou tem outro identificador e **a mesma
    árvore** da branch que o originou: é por isso que a árvore é a medida que
    sobrevive ao merge, e o identificador não.
    """
    out = _git(
        path,
        "log",
        "--remotes",
        f"--max-count={HISTORY_DEPTH}",
        "--pretty=%H\t%T",
    )
    commits: set[str] = set()
    trees: set[str] = set()
    for line in out.splitlines():
        sha, _, tree = line.partition("\t")
        if tree:
            commits.add(sha)
            trees.add(tree)
    return commits, trees


def _stashes(path: Path) -> list[dict[str, Any]]:
    """Os stashes do repositório, e se a branch de cada um ainda existe.

    O stash é do repositório, não da árvore de trabalho: worktree e pai compartilham
    `refs/stash`, e lê-lo nos dois contaria o mesmo stash várias vezes.
    """
    listing = _git(path, "stash", "list", "--format=%gd\t%H\t%gs")
    rows = [line.split("\t", 2) for line in listing.splitlines() if line.count("\t") >= 2]
    if not rows:
        return []

    alive = {
        line.strip()
        for line in _git(
            path, "for-each-ref", "--format=%(refname:short)", "refs/heads"
        ).splitlines()
        if line.strip()
    }
    alive.update(
        line.strip().split("/", 1)[-1]
        for line in _git(
            path, "for-each-ref", "--format=%(refname:strip=2)", "refs/remotes"
        ).splitlines()
        if line.strip()
    )

    return [
        {
            "ref": ref,
            "sha": sha,
            "branch": _stash_branch(subject),
            "message": subject,
            "branch_alive": _stash_branch(subject) in alive,
        }
        for ref, sha, subject in rows
    ]


def _stash_branch(subject: str) -> str:
    """A branch em que o stash nasceu, lida do assunto do reflog.

    As duas formas que o git escreve são `WIP on <branch>: ...` e `On <branch>: ...`.
    Um assunto que não é nenhuma das duas devolve vazio, e vazio nunca casa com
    branch nenhuma: um stash que não se sabe de onde veio não é órfão por dedução.
    """
    text = subject.strip()
    for prefix in ("WIP on ", "On "):
        if text.startswith(prefix):
            return text[len(prefix) :].split(":", 1)[0].strip()
    return ""


def _worktree_paths(repo: Path) -> list[Path]:
    """As árvores de trabalho penduradas neste repositório, onde quer que morem.

    As podáveis ficam de fora: o diretório delas já não existe, e planejar mover ou
    apagar o que não está lá seria plano sobre fantasma.

    A lista sai inteira, inclusive as de fora da raiz, porque ela serve a duas
    perguntas. Só uma delas é sobre layout, e essa filtra pela raiz; a outra é
    sobre o que o repositório carrega de sujo, e para essa uma árvore em diretório
    temporário conta tanto quanto uma vizinha.
    """
    listing = _git(repo, "worktree", "list", "--porcelain")
    found: list[Path] = []
    for block in listing.split("\n\n"):
        lines = [line for line in block.splitlines() if line]
        if not lines or not lines[0].startswith("worktree "):
            continue
        path = Path(lines[0].removeprefix("worktree ").strip())
        prunable = any(line.startswith("prunable") for line in lines)
        if prunable or path == repo or not path.is_dir():
            continue
        found.append(path)
    return found


def _without_worktrees(dirty: list[str], repo: Path, hanging: list[Path]) -> list[str]:
    """Tira da lista de sujo o que na verdade é árvore de trabalho deste repositório.

    Um worktree aninhado que o `.gitignore` do repositório não cobre aparece como
    diretório não rastreado, e o preflight o leria como trabalho a preservar. Ele
    não é: é uma árvore que o próprio plano já conhece, com branch e remote
    próprios. Commitá-lo enfiaria um repositório dentro do outro, que é dano, e
    não preservação.
    """
    if not hanging:
        return dirty
    return [
        name
        for name in dirty
        if not any(_at_or_under(repo / name.rstrip("/"), tree) for tree in hanging)
    ]


def _at_or_under(path: Path, tree: Path) -> bool:
    return path == tree or tree in path.parents or path in tree.parents


def build_observed(raw: Mapping[str, Any]) -> Observed:
    """Do JSON cru para o tipo que o planner recebe. Sem julgamento nenhum."""
    return Observed(
        org=raw.get("org") or "",
        root=raw.get("root") or "",
        org_repos=tuple(raw.get("org_repos") or ()),
        dirs=tuple(_work_dir(entry) for entry in raw.get("dirs") or ()),
    )


def _work_dir(entry: Mapping[str, Any]) -> WorkDir:
    return WorkDir(
        path=entry["path"],
        kind=entry.get("kind") or PLAIN,
        remote=entry.get("remote") or "",
        parent=entry.get("parent") or "",
        head=entry.get("head") or "",
        dirty=tuple(entry.get("dirty") or ()),
        branches=tuple(
            Branch(
                name=item["name"],
                content_on_remote=bool(item.get("content_on_remote")),
                commit_on_remote=bool(item.get("commit_on_remote")),
            )
            for item in entry.get("branches") or ()
        ),
        stashes=tuple(
            Stash(
                ref=item["ref"],
                sha=item.get("sha") or "",
                branch=item.get("branch") or "",
                message=item.get("message") or "",
                branch_alive=bool(item.get("branch_alive")),
            )
            for item in entry.get("stashes") or ()
        ),
    )


def observed_to_dict(observed: Observed) -> dict[str, Any]:
    """O retrato observado, de volta a JSON legível. Igual aos subpacotes irmãos."""
    return {
        "org": observed.org,
        "root": observed.root,
        "org_repos": list(observed.org_repos),
        "dirs": [_dir_to_dict(entry) for entry in observed.dirs],
    }


def _dir_to_dict(entry: WorkDir) -> dict[str, Any]:
    return {
        "path": entry.path,
        "kind": entry.kind,
        "remote": entry.remote,
        "parent": entry.parent,
        "head": entry.head,
        "dirty": list(entry.dirty),
        "branches": [
            {
                "name": branch.name,
                "content_on_remote": branch.content_on_remote,
                "commit_on_remote": branch.commit_on_remote,
            }
            for branch in entry.branches
        ],
        "stashes": [
            {
                "ref": stash.ref,
                "sha": stash.sha,
                "branch": stash.branch,
                "message": stash.message,
                "branch_alive": stash.branch_alive,
            }
            for stash in entry.stashes
        ],
    }
