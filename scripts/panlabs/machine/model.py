"""O estado observado da máquina, depois de o JSON cru virar tipo.

A fronteira com o sistema de arquivos é `observe.py`; aqui o dado já tem forma.

Uma distinção carrega quase toda esta issue: um caminho tem o **nome pelo qual
foi escrito** e o **alvo em que ele resolve**, e os dois divergem quando há link
no caminho. Negar leitura pelo nome escrito bloqueia a ferramenta e deixa o
comando de terminal equivalente passar, porque o shell fala com o alvo. Por isso
`resolved` é campo de primeira classe, e não um detalhe que o applier calcula.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "CredentialPath",
    "Link",
    "Observed",
    "RetireDir",
    "VendoredSkill",
]


@dataclass(frozen=True)
class Link:
    """Um nome que precisa ser alcançável pelo nome real, e onde ele aponta hoje.

    Dois campos porque são duas perguntas diferentes, e confundi-las custa:

    - `points_to` é o alvo **imediato** do link, e é o que responde "este nome
      aponta para onde eu pedi?". Comparar pelo alvo final replanejaria para
      sempre todo link cujo alvo é, ele mesmo, um link. O gerenciador de runtime
      faz exatamente isso: ele mantém um `latest` que reaponta a cada upgrade, e é
      justamente por isso que se pede o link para `latest` e não para a versão.
    - `resolved` é o fim da cadeia, e é o que responde "onde este nome mora de
      verdade?". É essa a pergunta que decide se a remoção de um diretório
      deixaria a máquina sem runtime, e ali só o fim da cadeia é seguro.

    Vazio significa que o nome não existe no diretório de binários. Um alias de
    shell não aparece aqui de propósito: alias não existe em subprocesso, que é
    exatamente como o agente roda, então para este planner ele é ausência.

    `anchored_target` é a terceira pergunta, e ela nasceu de um defeito real: o
    nome apontava exatamente para onde o dado pedia e mesmo assim não rodava.
    Existe alvo que só funciona no próprio diretório, porque calcula o que
    executar a partir de `dirname $0`. Alcançado por link, `$0` passa a ser o
    link, e ele procura o que executar ao lado do link. Apontar para o alvo
    pedido e ser alcançável são coisas diferentes, e `points_to` sozinho não
    distingue as duas.
    """

    name: str
    points_to: str = ""
    resolved: str = ""
    anchored_target: bool = False

    @property
    def present(self) -> bool:
        return bool(self.points_to or self.resolved)

    @property
    def reachable(self) -> bool:
        """O nome existe e roda pelo nome, que é o único sentido que importa aqui."""
        return self.present and not self.anchored_target


@dataclass(frozen=True)
class RetireDir:
    """Um diretório cuja remoção já está decidida, e o seu tamanho medido."""

    path: str
    present: bool = False
    bytes: int = 0


@dataclass(frozen=True)
class CredentialPath:
    """Um lugar de credencial: como foi escrito, onde resolve, e se tem conteúdo.

    `entries == 0` num diretório que existe é o caso que dimensiona o raio real:
    um diretório suspeito e vazio não guarda credencial nenhuma hoje. Ele continua
    valendo negação, mas por antecipação, e o plano diz qual dos dois motivos é.
    """

    path: str
    present: bool = False
    resolved: str = ""
    is_dir: bool = True
    entries: int = 0

    @property
    def is_linked(self) -> bool:
        """O nome escrito difere do alvo: é aqui que a negação vaza pelo shell."""
        return self.present and self.resolved != self.path


@dataclass(frozen=True)
class VendoredSkill:
    """Uma skill que existe dentro de um repositório, com nome e endereço."""

    repo: str
    name: str
    path: str


@dataclass(frozen=True)
class Observed:
    """O retrato da máquina que o planner recebe. Nada aqui é decisão."""

    links: tuple[Link, ...] = ()
    retire: tuple[RetireDir, ...] = ()
    credentials: tuple[CredentialPath, ...] = ()
    denylist: tuple[str, ...] = ()
    statusline: str = ""
    global_skills: tuple[str, ...] = ()
    vendored_skills: tuple[VendoredSkill, ...] = ()

    def link(self, name: str) -> Link:
        for item in self.links:
            if item.name == name:
                return item
        return Link(name=name)
