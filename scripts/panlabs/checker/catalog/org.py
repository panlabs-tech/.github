"""Os itens invariantes: cobrados de todo repositório, de todo tipo e stack.

Um item só mora aqui se a ausência dele é deriva em **qualquer** repositório da
org, sem condição nenhuma. Na dúvida, o item é de stack ou de tipo: um invariante
falso cobra de quem não deve, e é o falso positivo mais caro que existe aqui,
porque ele desgasta a matriz inteira.

**Dois itens que a prosa da spec listou sob stack e que moram aqui**, e a mudança
de endereço é deliberada: o contrato de nomes de status e a referência à CI
compartilhada. Os dois valem para **todo** repositório, inclusive o de stack
vazia, onde o rollup passa trivialmente e é justamente esse o ponto. Um item de
eixo stack precisa de um valor de stack para aparecer na matriz, e um repositório
sem superfície nenhuma não tem nenhum: escrevê-los como item de stack os deixaria
sem escopo exatamente no repositório que eles existem para servir.

Os itens são **construídos a partir do dado** (`config/anatomy.json` e
`config/org.json`), e não constantes: o catálogo decide que item existe e em que
eixo ele é avaliado, e o valor que ele cobra é dado versionado. Uma dimensão
ainda não decidida no dado simplesmente não gera item, pela mesma regra que rege
todo planner deste repo.
"""

from __future__ import annotations

from collections.abc import Sequence

from panlabs.checker.catalog.item import (
    ORG,
    AnatomyItem,
    always,
    declared,
    has_file,
    matches_any,
    missing,
)
from panlabs.checker.config import Anatomy, PathRule
from panlabs.checker.model import RepoObserved
from panlabs.org.config import Desired

__all__ = ["items"]


def items(anatomy: Anatomy, desired: Desired) -> tuple[AnatomyItem, ...]:
    """Os invariantes de org, na ordem em que aparecem na matriz."""
    built: list[AnatomyItem] = [_readme(), _license_exists()]
    built += _license_uniform(anatomy)
    built += _agent_entrypoint(anatomy)
    built += _agent_docs(anatomy)
    built += _triage_labels_slot(anatomy)
    built += _no_stale_tooling(anatomy)
    built += _no_vendored_equipment(anatomy)
    built += _local_gate(anatomy)
    built += _shared_ci(anatomy)
    built += _status_contract(anatomy)
    built += _vitrine(desired)
    return tuple(built)


# --- o núcleo universal -------------------------------------------------------


def _readme() -> AnatomyItem:
    return AnatomyItem(
        id="readme-exists",
        scope=ORG,
        applies=always,
        satisfied=lambda repo: repo.has_readme,
        motivo=lambda repo: f"{repo.name} não tem README",
    )


def _license_exists() -> AnatomyItem:
    return AnatomyItem(
        id="license-exists",
        scope=ORG,
        applies=always,
        satisfied=lambda repo: repo.has_license,
        motivo=lambda repo: f"{repo.name} não tem LICENSE",
    )


def _license_uniform(anatomy: Anatomy) -> list[AnatomyItem]:
    """A licença é uniforme na org, e o item só cobra de quem já tem alguma.

    Cobrar uniformidade de quem não tem licença nenhuma produziria duas linhas
    para o mesmo conserto, e a segunda não diria nada que a primeira já não diga.
    """
    uniform = anatomy.uniform_license
    if uniform is None:
        return []
    return [
        AnatomyItem(
            id="license-uniform",
            scope=ORG,
            applies=lambda repo: repo.has_license,
            satisfied=lambda repo: repo.license == uniform,
            motivo=lambda repo: (
                f"{repo.name} tem licença {repo.license or 'não identificada pela plataforma'}, "
                f"e a licença uniforme da org é {uniform}"
            ),
        )
    ]


# --- orientação de agente -----------------------------------------------------


def _agent_entrypoint(anatomy: Anatomy) -> list[AnatomyItem]:
    """O genérico é a fonte-da-verdade; o do agente primário o referencia.

    O segundo item só se aplica onde o arquivo do agente primário existe: um
    repositório sem agente primário configurado não deve nada. Onde ele existe,
    ele **precisa** apontar para o genérico -- é essa amarra que mata o fóssil de
    um genérico que já não corresponde ao conteúdo real.
    """
    generic, primary = anatomy.agent_entrypoint_generic, anatomy.agent_entrypoint_primary
    if generic is None or primary is None:
        return []
    return [
        AnatomyItem(
            id="agent-entrypoint-generico",
            scope=ORG,
            applies=always,
            satisfied=has_file(generic),
            motivo=lambda repo: (
                f"{repo.name} não tem {generic}, o arquivo genérico de orientação do agente "
                "que é a fonte-da-verdade"
            ),
        ),
        AnatomyItem(
            id="agent-entrypoint-primario-referencia-generico",
            scope=ORG,
            applies=has_file(primary),
            satisfied=lambda repo: generic in (repo.content(primary) or ""),
            motivo=lambda repo: (
                f"{repo.name} tem {primary} que não referencia {generic}: os dois descrevem "
                "o repositório por conta própria e podem divergir sem que nada acuse"
            ),
        ),
    ]


def _agent_docs(anatomy: Anatomy) -> list[AnatomyItem]:
    """Os documentos de nome fixo. Os condicionais não geram item nenhum.

    Um condicional legitimamente ausente **não é deriva**, e a forma de garantir
    isso é não escrever item para ele: eles moram no dado para ficar declarado
    que ninguém os cobra, não para serem cobrados.
    """
    required = anatomy.agent_docs_required
    if required is None:
        return []
    return [
        AnatomyItem(
            id="agent-docs-obrigatorios",
            scope=ORG,
            applies=always,
            satisfied=lambda repo: not missing(repo, required),
            motivo=lambda repo: (
                f"{repo.name} não tem {', '.join(missing(repo, required))}: "
                "documento de configuração de agente com nome fixo"
            ),
        )
    ]


def _triage_labels_slot(anatomy: Anatomy) -> list[AnatomyItem]:
    """O vocabulário de labels é slot: obriga a declaração, nunca o valor.

    Dois dialetos convivem na frota, um com prefixo de namespace e família
    ortogonal adicional e outro com o canônico puro, e **os dois passam**. O que
    reprova é o slot vazio ou não declarado, e por isso o teste é o documento
    dizer alguma coisa e nomear ao menos uma label -- nunca *qual* label. Nenhum
    dialeto está cravado aqui, e essa é a propriedade que um teste guarda.
    """
    required = anatomy.agent_docs_required
    if required is None:
        return []
    doc = next((path for path in required if path.endswith("triage-labels.md")), None)
    if doc is None:
        return []
    return [
        AnatomyItem(
            id="triage-labels-slot-declarado",
            scope=ORG,
            applies=has_file(doc),
            satisfied=lambda repo: _names_a_label(repo, doc),
            motivo=lambda repo: (
                f"{repo.name} tem {doc} sem vocabulário declarado: o slot existe e está vazio, "
                "e um script de frota não tem de onde ler a label deste repositório"
            ),
        )
    ]


def _names_a_label(repo: RepoObserved, doc: str) -> bool:
    """O documento diz alguma coisa e nomeia ao menos uma label.

    A label é nomeada em `código inline` nos dois dialetos da frota, que é como
    um documento distingue o nome da string do resto da prosa. Ler a marcação em
    vez do valor é o que mantém o dialeto fora do código.
    """
    return declared(repo, doc) and "`" in (repo.content(doc) or "")


# --- o que o repositório não versiona -----------------------------------------


def _no_stale_tooling(anatomy: Anatomy) -> list[AnatomyItem]:
    rules = anatomy.stale_tool_paths
    if rules is None:
        return []
    return [
        AnatomyItem(
            id="sem-configuracao-stale-de-ferramenta",
            scope=ORG,
            applies=always,
            satisfied=lambda repo: not matches_any(repo, rules),
            motivo=lambda repo: (
                f"{repo.name} versiona configuração fora da toolchain decidida: "
                f"{_why_hits(repo, rules)}. "
                "Preflight antes de remover: aquilo é candidato a promoção global?"
            ),
        )
    ]


def _no_vendored_equipment(anatomy: Anatomy) -> list[AnatomyItem]:
    rules = anatomy.global_equipment_paths
    if rules is None:
        return []
    return [
        AnatomyItem(
            id="sem-equipamento-global-versionado",
            scope=ORG,
            applies=always,
            satisfied=lambda repo: not matches_any(repo, rules),
            motivo=lambda repo: (
                f"{repo.name} versiona equipamento global: {_why_hits(repo, rules)}. "
                "Equipamento global mora num lugar só, e a des-vendorização acontece "
                "dentro do retrofit deste repositório"
            ),
        )
    ]


def _why_hits(repo: RepoObserved, rules: Sequence[PathRule]) -> str:
    """Os prefixos que casaram, cada um com o motivo declarado no dado.

    O motivo vem do dado e não daqui porque é ele que torna a linha revisável:
    "tem `.serena/`" manda o operador adivinhar, "ferramenta de indexação fora da
    toolchain decidida" já diz o que fazer com aquilo.
    """
    hit_rules: list[PathRule] = []
    for _, rule in matches_any(repo, rules):
        if rule not in hit_rules:
            hit_rules.append(rule)
    return "; ".join(f"`{rule.prefix}` ({rule.why})" for rule in hit_rules)


# --- os dois portões e o contrato de status -----------------------------------


def _local_gate(anatomy: Anatomy) -> list[AnatomyItem]:
    """Três itens, porque são três consertos separados.

    O portão pode existir sem padrão de mensagem, e ter padrão de mensagem sem
    scan de segredos. Uma linha só na matriz esconderia qual dos três falta, e o
    retrofit precisa saber.
    """
    gate = anatomy.local_gate
    if gate is None:
        return []
    return [
        AnatomyItem(
            id="portao-local-existe",
            scope=ORG,
            applies=always,
            satisfied=has_file(gate.file),
            motivo=lambda repo: (
                f"{repo.name} não tem {gate.file}: sem portão local, todo erro barato "
                "só é pego na CI"
            ),
        ),
        AnatomyItem(
            id="padrao-de-mensagem-de-commit",
            scope=ORG,
            applies=has_file(gate.file),
            satisfied=lambda repo: gate.commit_message_tool in (repo.content(gate.file) or ""),
            motivo=lambda repo: (
                f"{repo.name} tem portão local que não declara {gate.commit_message_tool}: "
                "a mensagem de commit não é verificada antes de aterrissar"
            ),
        ),
        AnatomyItem(
            id="scan-de-segredos-antes-do-commit",
            scope=ORG,
            applies=has_file(gate.file),
            satisfied=lambda repo: gate.secret_scan_tool in (repo.content(gate.file) or ""),
            motivo=lambda repo: (
                f"{repo.name} tem portão local que não declara {gate.secret_scan_tool}: "
                "um segredo só é barrado depois de já estar no histórico local"
            ),
        ),
    ]


def _shared_ci(anatomy: Anatomy) -> list[AnatomyItem]:
    """A CI referencia os workflows compartilhados, e ninguém copia YAML.

    Vale para todo repositório, inclusive o de stack vazia: mesmo sem perna por
    superfície, o scan de segredos e o rollup vêm de lá. A exceção de quem
    publica os workflows é dado declarado, e não um `if` aqui dentro.
    """
    ci = anatomy.shared_ci
    if ci is None:
        return []
    return [
        AnatomyItem(
            id="ci-referencia-workflows-compartilhados",
            scope=ORG,
            applies=always,
            satisfied=lambda repo: ci.referenced_by(repo.name, repo.content(ci.caller) or ""),
            motivo=lambda repo: (
                f"{repo.name} não tem {ci.caller} referenciando {ci.ref}: "
                "os quatro arquivos de CI da frota nasceram copiados um do outro e divergiram "
                "entre 48% e 86% em sete semanas, e origem comum não impede deriva"
            ),
        )
    ]


def _status_contract(anatomy: Anatomy) -> list[AnatomyItem]:
    """O mesmo conjunto de nomes de status, com zero, uma ou duas superfícies.

    É o que faz a lista fixa de required checks da spec de Org sobreviver a stack
    variável: o rollup declara dependência das pernas por superfície e reporta um
    status único, e existe até onde não há perna nenhuma.
    """
    jobs = anatomy.status_contract_jobs
    ci = anatomy.shared_ci
    if jobs is None or ci is None:
        return []
    return [
        AnatomyItem(
            id="contrato-de-nomes-de-status",
            scope=ORG,
            applies=has_file(ci.caller),
            satisfied=lambda repo: not _missing_jobs(repo, ci.caller, jobs),
            motivo=lambda repo: (
                f"{repo.name} não publica {', '.join(_missing_jobs(repo, ci.caller, jobs))} "
                f"em {ci.caller}: o required check de nome fixo espera para sempre um status "
                "que ninguém publica"
            ),
        )
    ]


def _missing_jobs(repo: RepoObserved, caller: str, jobs: Sequence[str]) -> tuple[str, ...]:
    """Os jobs de id fixo que o caller não declara.

    Procura o id no começo de uma linha indentada, que é a única forma em que uma
    chave de `jobs:` aparece em YAML. Casar o nome em qualquer lugar do arquivo
    aprovaria um repositório por causa de um comentário que cita o nome.
    """
    content = repo.content(caller) or ""
    declared_ids = {
        line.strip().rstrip(":")
        for line in content.splitlines()
        if line.startswith("  ")
        and not line.startswith("   ")
        and line.strip().endswith(":")
        and not line.strip().startswith("#")
    }
    return tuple(job for job in jobs if job not in declared_ids)


# --- a vitrine que não mora no working tree -----------------------------------


def _vitrine(desired: Desired) -> list[AnatomyItem]:
    """Descrição, topics e wiki: a travessia deliberada da fronteira com a spec de Org.

    A fronteira de *decisão* continua lá, e é por isso que o valor é lido de
    `config/org.json` em vez de cravado aqui. A de *verificação* atravessa de
    propósito: nenhum dos três mora no working tree, e sem o checker eles ficariam
    sem vigia nenhum.
    """
    built: list[AnatomyItem] = []

    descriptions = desired.repo_descriptions
    if descriptions is not None:
        built.append(
            AnatomyItem(
                id="descricao-declarada",
                scope=ORG,
                applies=always,
                satisfied=lambda repo: _matches_text(repo.description, descriptions.get(repo.name)),
                motivo=lambda repo: _text_motivo(
                    repo.name, repo.description, descriptions.get(repo.name)
                ),
            )
        )

    topics = desired.repo_topics
    if topics is not None:
        built.append(
            AnatomyItem(
                id="topics-declarados",
                scope=ORG,
                applies=always,
                satisfied=lambda repo: _matches_topics(repo.topics, topics.get(repo.name)),
                motivo=lambda repo: _topics_motivo(repo.name, repo.topics, topics.get(repo.name)),
            )
        )

    if desired.wiki is not None:
        enabled = bool(desired.wiki.get("enabled"))
        exceptions = desired.wiki_exceptions()
        built.append(
            AnatomyItem(
                id="wiki-conforme-decidido",
                scope=ORG,
                applies=lambda repo: repo.name not in exceptions,
                satisfied=lambda repo: repo.has_wiki == enabled,
                motivo=lambda repo: (
                    f"{repo.name} tem wiki {'ligada' if repo.has_wiki else 'desligada'}, "
                    f"e a org decidiu {'ligada' if enabled else 'desligada'}: "
                    "superfície vazia que ninguém mantém"
                ),
            )
        )

    return built


def _matches_text(observed: str | None, wanted: str | None) -> bool:
    """Com texto governado, o valor exato; sem ele, só a exigência de existir.

    Um repositório fora do dado não tem texto governado, e inventar o texto dele
    não é trabalho de script: o que se cobra ali é que ele tenha *alguma* coisa.
    """
    if wanted is None:
        return bool((observed or "").strip())
    return observed == wanted


def _matches_topics(observed: frozenset[str], wanted: Sequence[str] | None) -> bool:
    if wanted is None:
        return bool(observed)
    return observed == frozenset(str(topic) for topic in wanted)


def _text_motivo(name: str, observed: str | None, wanted: str | None) -> str:
    if wanted is None:
        return f"{name} não tem descrição nenhuma, e a listagem da org fica ilegível sem abrir nada"
    return f"{name} tem descrição divergente do declarado em config/org.json: {observed!r}"


def _topics_motivo(name: str, observed: frozenset[str], wanted: Sequence[str] | None) -> str:
    if wanted is None:
        return f"{name} não tem topic nenhum, e a frota não é filtrável por tecnologia"
    return (
        f"{name} tem topics {sorted(observed)}, e config/org.json declara "
        f"{sorted(str(topic) for topic in wanted)}"
    )
