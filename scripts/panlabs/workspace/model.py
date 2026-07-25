"""O estado observado do espaço de trabalho, depois de o disco virar tipo.

A fronteira com o sistema de arquivos e com o `git` é `observe.py`; aqui o dado
já tem forma e ainda não tem decisão nenhuma.

Uma distinção carrega quase toda esta issue: uma branch tem **conteúdo** e tem
**identificador**, e os dois divergem sob squash-merge. Por isso `Branch` guarda
os dois como campos separados, e não um só "está no remote": foi confundir os
dois que gerou o alarme falso de 30 commits em 22 branches supostamente ausentes
de todo remote, todas na verdade idênticas ao que já estava lá.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "EMPTY",
    "PLAIN",
    "REPO",
    "WORKTREE",
    "Branch",
    "Observed",
    "Stash",
    "WorkDir",
    "remote_parts",
]

EMPTY = "empty"
"""Diretório sem nenhuma entrada dentro. Sempre elegível ao descarte."""

PLAIN = "plain"
"""Diretório com conteúdo e sem git. Nunca elegível: sem remote, nada o substitui."""

REPO = "repo"
"""Um repositório git de verdade, dono do próprio diretório `.git`."""

WORKTREE = "worktree"
"""Uma árvore de trabalho pendurada num repositório pai, que ela nomeia."""


def remote_parts(url: str) -> tuple[str, str]:
    """Dono e nome do repositório, de qualquer das duas formas de endereço.

    Ler o dono do remote é o que separa repo da org de repo pessoal, e é isso, e
    não o nome do diretório, que decide. Um endereço que não tem as duas partes
    devolve vazio, e vazio significa "não dá para afirmar nada sobre este dono".
    """
    if not url:
        return ("", "")

    text = url.removesuffix(".git").removesuffix("/")
    if "//" in text:
        text = text.split("//", 1)[1]
        text = text.split("/", 1)[1] if "/" in text else ""
    elif ":" in text:
        text = text.split(":", 1)[1]

    parts = [part for part in text.split("/") if part]
    if len(parts) < 2:
        return ("", "")
    return (parts[-2], parts[-1])


@dataclass(frozen=True)
class Branch:
    """Uma branch local, e as duas perguntas diferentes que se faz a ela.

    - `content_on_remote` responde "esta árvore já está em algum remote?", e é a
      **única** que decide qualquer coisa aqui. Sob squash-merge é ela que continua
      verdadeira depois de a branch aterrissar.
    - `commit_on_remote` responde "este identificador está em algum remote?", e é
      justamente a pergunta que o squash-merge faz mentir. Ela existe no modelo
      para ser medida e para o plano poder dizer que **não** a usou.
    """

    name: str
    content_on_remote: bool = False
    commit_on_remote: bool = False


@dataclass(frozen=True)
class Stash:
    """Um stash, e se a branch em que ele nasceu ainda existe em algum lugar.

    `branch_alive` é falso quando a branch sumiu do local **e** de todo remote.
    Um stash assim não se aplica a nada, e é o único que o plano descarta.
    """

    ref: str
    sha: str
    branch: str = ""
    message: str = ""
    branch_alive: bool = False


@dataclass(frozen=True)
class WorkDir:
    """Um diretório do espaço de trabalho, como o disco o entrega.

    `dirty` é lista de **arquivo**, não de diretório, porque o default do `git`
    colapsa diretório não rastreado num item só e subconta o que se perderia.

    `head` vazio é HEAD destacada: dá para commitar, e não dá para dizer em que
    branch. O plano trata os dois casos, e por isso a diferença chega até aqui.
    """

    path: str
    kind: str = PLAIN
    remote: str = ""
    parent: str = ""
    head: str = ""
    dirty: tuple[str, ...] = ()
    branches: tuple[Branch, ...] = ()
    stashes: tuple[Stash, ...] = ()

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def is_git(self) -> bool:
        return self.kind in (REPO, WORKTREE)

    @property
    def owner(self) -> str:
        return remote_parts(self.remote)[0]

    @property
    def repo_name(self) -> str:
        return remote_parts(self.remote)[1]

    @property
    def unpushed(self) -> tuple[Branch, ...]:
        """As branches cujo **conteúdo** não está em remote nenhum.

        Nunca as de identificador divergente: essas são as que já aterrissaram.
        """
        return tuple(branch for branch in self.branches if not branch.content_on_remote)

    @property
    def only_local(self) -> bool:
        """Tem alguma coisa aqui que só existe neste disco?"""
        return bool(self.dirty or self.unpushed)


@dataclass(frozen=True)
class Observed:
    """O retrato do espaço de trabalho que o planner recebe.

    `org_repos` vem da org viva, nunca de um manifesto: é essa escolha que faz
    repo novo entrar sozinho e impede a regra de divergir da realidade.
    """

    org: str = ""
    root: str = ""
    org_repos: tuple[str, ...] = ()
    dirs: tuple[WorkDir, ...] = ()

    def at(self, path: str) -> WorkDir | None:
        for entry in self.dirs:
            if entry.path == path:
                return entry
        return None
