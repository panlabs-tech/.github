"""O dado que o checker lê: três arquivos, com naturezas diferentes.

`repo-types.json` é **classificação**: tipos são nomeados e finitos (`ANATOMY.md`),
e classificar um repositório é escolha do operador quando ele nasce, não um
cálculo do checker. Um repositório ausente do mapa, ou com valor `null`, ainda não
foi classificado: os itens de escopo tipo não o alcançam, e isso não é deriva.

`checker.json` é **parâmetro de leitura**: o conjunto de arquivos cujo conteúdo é
observado. Ele é declarado porque a alternativa é varredura cega, e porque o custo
por repositório precisa caber numa consulta só. Aqui, ao contrário de um planner,
não decidido e decidido-como-vazio têm o mesmo efeito -- nada é lido --, porque
observação não planeja nada; a distinção que importa vive nos planners.

`anatomy.json` é o **valor que cada item do catálogo cobra**. O catálogo decide
que item existe e em que eixo ele é avaliado; o valor que ele exige é dado, pela
mesma razão que rege o resto do repo. Aqui `null` volta a significar **ainda não
decidido**, como num planner: o item existe, é executável, e não avalia nada
enquanto a dimensão não for decidida -- e o CLI diz isso em voz alta, para que um
plano vazio não seja lido como conformidade.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_ANATOMY_PATH",
    "DEFAULT_CHECKER_CONFIG_PATH",
    "DEFAULT_REPO_TYPES_PATH",
    "VALID_TYPES",
    "Anatomy",
    "Aplicacao",
    "LocalGate",
    "PathRule",
    "SharedCi",
    "Surface",
    "load_anatomy",
    "load_read_files",
    "load_repo_types",
]

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"

DEFAULT_REPO_TYPES_PATH = CONFIG_DIR / "repo-types.json"
DEFAULT_CHECKER_CONFIG_PATH = CONFIG_DIR / "checker.json"
DEFAULT_ANATOMY_PATH = CONFIG_DIR / "anatomy.json"

VALID_TYPES = frozenset({"aplicacao", "modulo-infraestrutura", "skills", "meta", "dotfiles"})
"""Os cinco tipos nomeados e finitos de `ANATOMY.md`. Nenhum sexto tipo existe."""

KNOWN_KEYS = ("read_files",)


def load_repo_types(path: Path = DEFAULT_REPO_TYPES_PATH) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    types = {
        key: value
        for key, value in raw.items()
        if not key.startswith("_") and isinstance(value, str)
    }

    unknown = sorted(set(types.values()) - VALID_TYPES)
    if unknown:
        raise ValueError(
            f"tipo desconhecido em {path}: {', '.join(unknown)}; "
            f"os cinco tipos válidos (ANATOMY.md) são {', '.join(sorted(VALID_TYPES))}"
        )

    return types


def load_read_files(path: Path = DEFAULT_CHECKER_CONFIG_PATH) -> tuple[str, ...]:
    """Os arquivos cujo conteúdo é lido, na ordem declarada.

    A ordem é preservada porque ela é a ordem dos apelidos da consulta, e um
    conjunto lido em ordem instável produziria retratos que diferem sem que nada
    tenha mudado no repositório -- e o retrato é fixture comparável.
    """
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    unknown = sorted(k for k in raw if not k.startswith("_") and k not in KNOWN_KEYS)
    if unknown:
        raise ValueError(
            f"chave desconhecida em {path}: {', '.join(unknown)}; "
            f"chaves válidas: {', '.join(KNOWN_KEYS)}"
        )

    declared = raw.get("read_files")
    if declared is None:
        return ()
    return _paths(declared, path)


# --- o valor que cada item do catálogo cobra ----------------------------------


@dataclass(frozen=True)
class PathRule:
    """Um caminho que a anatomia proíbe, com o motivo pelo qual ele não pertence.

    O motivo viaja junto do prefixo porque ele vira o texto da linha da matriz:
    "tem `.serena/`" não é revisável, "tem ferramenta de indexação fora da
    toolchain decidida" é. Um prefixo terminado em `/` casa o diretório inteiro;
    sem barra, casa o caminho exato.
    """

    prefix: str
    why: str

    def matches(self, path: str) -> bool:
        return path.startswith(self.prefix) if self.prefix.endswith("/") else path == self.prefix


@dataclass(frozen=True)
class LocalGate:
    """O portão 1: o que roda antes do commit, e o que ele precisa declarar."""

    file: str
    commit_message_tool: str
    secret_scan_tool: str


@dataclass(frozen=True)
class SharedCi:
    """A referência à CI compartilhada, e a exceção de quem a publica.

    A exceção é dado declarado, e não um `if` no catálogo: o repo que publica os
    workflows os referencia por caminho local, porque um caller no mesmo repo
    resolve contra o próprio commit.
    """

    caller: str
    ref: str
    publisher: str
    publisher_ref: str

    def referenced_by(self, repo_name: str, content: str) -> bool:
        if self.ref in content:
            return True
        return repo_name == self.publisher and self.publisher_ref in content


@dataclass(frozen=True)
class Surface:
    """O que uma superfície declara. `runtime_major` é a convergência da frota."""

    name: str
    runtime_file: str
    runtime_major: str | None
    gate_tool: str
    ci_workflow: str
    lockfiles: tuple[str, ...] | None


@dataclass(frozen=True)
class Aplicacao:
    """O que o tipo aplicação carrega além dos invariantes."""

    package_manager_lockfile: str
    package_manager_workspace: str
    foreign_lockfiles: tuple[str, ...]
    apps_dir: str
    container_build_file: str
    mcp_config: str
    mcp_env_placeholder: str
    env_example: str
    stateful_markers: tuple[str, ...]
    compose_files: tuple[str, ...]


@dataclass(frozen=True)
class Anatomy:
    """Os valores que o catálogo cobra, já lidos e tipados.

    Uma dimensão `None` está **ainda não decidida**, e o item que depende dela
    não avalia nada. `undecided` é o que o CLI reporta, para que ninguém leia
    silêncio como conformidade.
    """

    uniform_license: str | None = None
    agent_docs_required: tuple[str, ...] | None = None
    agent_docs_conditional: tuple[str, ...] | None = None
    agent_entrypoint_generic: str | None = None
    agent_entrypoint_primary: str | None = None
    stale_tool_paths: tuple[PathRule, ...] | None = None
    global_equipment_paths: tuple[PathRule, ...] | None = None
    local_gate: LocalGate | None = None
    shared_ci: SharedCi | None = None
    status_contract_jobs: tuple[str, ...] | None = None
    surfaces: Mapping[str, Surface] | None = None
    aplicacao: Aplicacao | None = None
    empty_stack_types: tuple[str, ...] | None = None
    meta_files: tuple[str, ...] | None = None

    @property
    def undecided(self) -> tuple[str, ...]:
        """As dimensões que ainda esperam decisão, pelo nome que o dado usa.

        Derivada dos próprios campos, e não de uma lista escrita ao lado: uma
        segunda lista dos mesmos nomes divergiria no primeiro campo novo, e o
        modo de falhar dela é silencioso -- a dimensão nova ficaria fora do
        aviso, que é exatamente o silêncio lido como conformidade.

        A convergência de versão maior é aninhada por superfície, e por isso vem
        pelo caminho completo: `surfaces.node.runtime_major` diz qual superfície
        espera decisão, e `surfaces` diria só que existem superfícies.
        """
        pending = [field.name for field in fields(self) if getattr(self, field.name, None) is None]
        for surface in (self.surfaces or {}).values():
            if surface.runtime_major is None:
                pending.append(f"surfaces.{surface.name}.runtime_major")
        return tuple(sorted(pending))


ANATOMY_KEYS = (
    "uniform_license",
    "agent_docs",
    "agent_entrypoint",
    "stale_tool_paths",
    "global_equipment_paths",
    "local_gate",
    "shared_ci",
    "status_contract",
    "surfaces",
    "aplicacao",
    "empty_stack_types",
    "meta_files",
)


def load_anatomy(path: Path = DEFAULT_ANATOMY_PATH) -> Anatomy:
    """Lê os valores que o catálogo cobra. Chave desconhecida é erro, não folga.

    Uma chave que ninguém lê é pior do que uma ausente: ela parece decidida e não
    governa nada. É a mesma checagem que os outros carregadores de dado do repo
    fazem, e pelo mesmo motivo.
    """
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    unknown = sorted(k for k in raw if not k.startswith("_") and k not in ANATOMY_KEYS)
    if unknown:
        raise ValueError(
            f"chave desconhecida em {path}: {', '.join(unknown)}; "
            f"chaves válidas: {', '.join(ANATOMY_KEYS)}"
        )

    agent_docs = _section(raw, "agent_docs")
    entrypoint = _section(raw, "agent_entrypoint")
    gate = _section(raw, "local_gate")
    ci = _section(raw, "shared_ci")
    contract = _section(raw, "status_contract")
    app = _section(raw, "aplicacao")

    return Anatomy(
        uniform_license=_str_or_none(raw.get("uniform_license")),
        agent_docs_required=_strs_or_none(agent_docs.get("required")),
        agent_docs_conditional=_strs_or_none(agent_docs.get("conditional")),
        agent_entrypoint_generic=_str_or_none(entrypoint.get("generic")),
        agent_entrypoint_primary=_str_or_none(entrypoint.get("primary")),
        stale_tool_paths=_rules_or_none(raw.get("stale_tool_paths")),
        global_equipment_paths=_rules_or_none(raw.get("global_equipment_paths")),
        local_gate=_local_gate(gate),
        shared_ci=_shared_ci(ci),
        status_contract_jobs=_strs_or_none(contract.get("jobs")),
        surfaces=_surfaces(raw.get("surfaces")),
        aplicacao=_aplicacao(app),
        empty_stack_types=_strs_or_none(raw.get("empty_stack_types")),
        meta_files=_strs_or_none(raw.get("meta_files")),
    )


def _section(raw: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = raw.get(key)
    return value if isinstance(value, Mapping) else {}


def _str_or_none(value: Any) -> str | None:
    return str(value) if isinstance(value, str) else None


def _strs_or_none(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return None
    return tuple(str(entry) for entry in value)


def _rules_or_none(value: Any) -> tuple[PathRule, ...] | None:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return None
    rules: list[PathRule] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        prefix, why = entry.get("prefix"), entry.get("why")
        if not isinstance(prefix, str) or not isinstance(why, str):
            raise ValueError(
                "cada regra de caminho precisa de `prefix` e `why`: motivo é obrigatório"
            )
        rules.append(PathRule(prefix=prefix, why=why))
    return tuple(rules)


def _local_gate(raw: Mapping[str, Any]) -> LocalGate | None:
    file = _str_or_none(raw.get("file"))
    commit = _str_or_none(raw.get("commit_message_tool"))
    secret = _str_or_none(raw.get("secret_scan_tool"))
    if file is None or commit is None or secret is None:
        return None
    return LocalGate(file=file, commit_message_tool=commit, secret_scan_tool=secret)


def _shared_ci(raw: Mapping[str, Any]) -> SharedCi | None:
    caller = _str_or_none(raw.get("caller"))
    ref = _str_or_none(raw.get("ref"))
    publisher = _str_or_none(raw.get("publisher"))
    publisher_ref = _str_or_none(raw.get("publisher_ref"))
    if caller is None or ref is None or publisher is None or publisher_ref is None:
        return None
    return SharedCi(caller=caller, ref=ref, publisher=publisher, publisher_ref=publisher_ref)


def _surfaces(value: Any) -> Mapping[str, Surface] | None:
    if not isinstance(value, Mapping):
        return None
    surfaces: dict[str, Surface] = {}
    for name, raw in value.items():
        if str(name).startswith("_") or not isinstance(raw, Mapping):
            continue
        runtime_file = _str_or_none(raw.get("runtime_file"))
        gate_tool = _str_or_none(raw.get("gate_tool"))
        ci_workflow = _str_or_none(raw.get("ci_workflow"))
        if runtime_file is None or gate_tool is None or ci_workflow is None:
            continue
        surfaces[str(name)] = Surface(
            name=str(name),
            runtime_file=runtime_file,
            runtime_major=_str_or_none(raw.get("runtime_major")),
            gate_tool=gate_tool,
            ci_workflow=ci_workflow,
            lockfiles=_strs_or_none(raw.get("lockfiles")),
        )
    return surfaces


def _aplicacao(raw: Mapping[str, Any]) -> Aplicacao | None:
    lockfile = _str_or_none(raw.get("package_manager_lockfile"))
    workspace = _str_or_none(raw.get("package_manager_workspace"))
    apps_dir = _str_or_none(raw.get("apps_dir"))
    container = _str_or_none(raw.get("container_build_file"))
    mcp = _str_or_none(raw.get("mcp_config"))
    placeholder = _str_or_none(raw.get("mcp_env_placeholder"))
    env_example = _str_or_none(raw.get("env_example"))
    foreign = _strs_or_none(raw.get("foreign_lockfiles"))
    markers = _strs_or_none(raw.get("stateful_markers"))
    compose = _strs_or_none(raw.get("compose_files"))
    fields = (lockfile, workspace, apps_dir, container, mcp, placeholder, env_example)
    if any(field is None for field in fields) or foreign is None or markers is None:
        return None
    if compose is None:
        return None
    return Aplicacao(
        package_manager_lockfile=str(lockfile),
        package_manager_workspace=str(workspace),
        foreign_lockfiles=foreign,
        apps_dir=str(apps_dir),
        container_build_file=str(container),
        mcp_config=str(mcp),
        mcp_env_placeholder=str(placeholder),
        env_example=str(env_example),
        stateful_markers=markers,
        compose_files=compose,
    )


def _paths(declared: Any, source: Path) -> tuple[str, ...]:
    if not isinstance(declared, Sequence) or isinstance(declared, str):
        raise ValueError(f"`read_files` em {source} precisa ser uma lista de caminhos")

    paths = [str(entry) for entry in declared]
    repeated = sorted({path for path in paths if paths.count(path) > 1})
    if repeated:
        raise ValueError(
            f"caminho repetido em `read_files` de {source}: {', '.join(repeated)}; "
            "cada arquivo já é lido uma vez por repositório, e repeti-lo só pagaria duas vezes "
            "pela mesma resposta"
        )
    return tuple(paths)
