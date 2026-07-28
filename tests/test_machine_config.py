"""A configuração desejada da máquina: dado versionado, e o que ele recusa.

Dois eixos. O primeiro é a leitura: `~` vira endereço desta máquina, e `null`
significa ainda não decidido, que é diferente de decidido-como-vazio. O segundo é
a recusa: um campo faltando num item de configuração tem que estourar na leitura,
porque descobri-lo no meio da aplicação seria o pior momento possível.

E um teste sobre o dado real de `config/machine.json`, porque ele é parte do
repositório e uma chave errada ali não é erro de máquina, é erro versionado.
"""

import json
import re
from pathlib import Path

import pytest

from panlabs.machine.config import DEFAULT_CONFIG_PATH, Desired, expand, load_desired


def test_a_tilde_path_becomes_an_address_on_this_machine():
    assert expand("~/x").startswith(str(Path.home()))
    assert expand("~/x").endswith("/x")


def test_an_absolute_path_is_left_alone():
    assert expand("/usr/bin/fdfind") == "/usr/bin/fdfind"


def test_an_absent_dimension_is_undecided_and_not_decided_as_empty():
    desired = Desired.from_dict({"bin_dir": "~/.local/bin"})

    assert "links" in desired.undecided
    assert desired.links is None
    assert not desired.is_decided


def test_a_dimension_decided_as_empty_is_decided():
    desired = Desired.from_dict({"links": []})

    assert "links" not in desired.undecided
    assert desired.links == ()


def test_an_unknown_key_is_refused_instead_of_ignored():
    with pytest.raises(ValueError, match="chave desconhecida"):
        Desired.from_dict({"lnks": []})


def test_a_key_starting_with_underscore_is_a_comment_and_is_allowed():
    """O dado carrega o motivo junto, e o motivo é lido por humano."""
    desired = Desired.from_dict({"_links": "por que esta dimensão existe", "links": []})

    assert desired.links == ()


def test_a_link_without_a_reason_is_refused():
    """Um item de plano sem motivo não é revisável, e o motivo vem do dado."""
    with pytest.raises(ValueError, match="sem os campos"):
        Desired.from_dict({"links": [{"name": "fd", "target": "/usr/bin/fdfind"}]})


def test_a_retire_entry_without_a_reason_is_refused():
    with pytest.raises(ValueError, match="sem os campos"):
        Desired.from_dict({"retire": [{"path": "~/.nvm"}]})


def test_a_secret_without_a_reason_is_refused():
    with pytest.raises(ValueError, match="sem os campos"):
        Desired.from_dict({"read_denylist": [{"path": "~/.aws"}]})


def test_a_dimension_that_should_be_a_list_is_refused_when_it_is_not():
    with pytest.raises(ValueError, match="esperava uma lista"):
        Desired.from_dict({"links": "fd"})


def test_a_promotion_declares_which_repo_it_reads_from():
    """Sem a origem declarada, a promoção dependeria da ordem do disco."""
    desired = Desired.from_dict(
        {"skills": {"promote": [{"name": "caveman", "source": "panlabs", "why": "órfã real"}]}}
    )

    assert desired.skills is not None
    assert desired.skills.promote[0].source == "panlabs"


# --- o dado real deste repositório -------------------------------------------


def test_the_versioned_config_loads_and_is_fully_decided():
    desired = load_desired()

    assert desired.is_decided, f"dimensões sem decisão: {desired.undecided}"


def test_every_discarded_skill_names_the_global_that_supersedes_it():
    """Descartar sem dizer quem já faz o trabalho não é revisável."""
    desired = load_desired()

    assert desired.skills is not None
    assert desired.skills.discard
    for move in desired.skills.discard:
        assert move.superseded_by, f"{move.name} descartada sem dizer quem a substitui"


def test_no_skill_is_both_promoted_and_discarded():
    desired = load_desired()

    assert desired.skills is not None
    promoted = {move.name for move in desired.skills.promote}
    discarded = {move.name for move in desired.skills.discard}
    assert not (promoted & discarded)


def test_the_versioned_config_denies_the_two_credential_stores_that_hold_something():
    """A spec dimensiona o raio real; o dado tem que cobrir os dois lugares dele."""
    raw = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))

    declared = {entry["path"] for entry in raw["read_denylist"]}
    assert {"~/.aws", "~/.ssh"} <= declared


# --- o portão local: as ferramentas que o executam ----------------------------


def test_the_shipped_config_declares_the_tools_the_local_gate_runs():
    """O portão 1 é declaração inerte enquanto o binário não é equipamento desta máquina.

    `docs/maquina.md` já classificava as duas como binário direto e já dizia que
    instalá-las é convergência de máquina. O que faltava era o dado que o planner
    lê, e enquanto faltou nenhum plano jamais as mencionou: o `lefthook.yml` de todo
    repo da frota era um arquivo que três itens da anatomia verificavam e que nada
    executava.
    """
    desired = load_desired()

    assert desired.tools is not None
    assert {tool.name for tool in desired.tools} >= {"lefthook", "gitleaks"}


def test_every_declared_tool_carries_the_command_that_installs_it():
    """Um plano que dissesse só "instale o lefthook" empurraria a decisão de volta."""
    desired = load_desired()

    assert desired.tools
    for tool in desired.tools:
        assert tool.install, f"{tool.name} declarada sem comando de instalação"
        assert tool.why, f"{tool.name} declarada sem motivo"


def test_no_tool_command_pins_a_version():
    """A classe destas ferramentas é "CLI que precisa ficar fresca".

    Um comando com versão cravada viraria fóssil no primeiro release, e o
    invariante passaria a exigir de volta a versão que alguém escreveu um dia.
    """
    desired = load_desired()

    assert desired.tools
    for tool in desired.tools:
        assert not re.search(r"\d+\.\d+\.\d+", tool.install), (
            f"{tool.name} pina versão no comando de instalação"
        )


def test_a_tool_is_not_declared_twice_as_a_link_too():
    """Duas dimensões sobre a mesma pergunta seriam duas verdades que divergem.

    `npx` e `uv` são cobrados como nome alcançável em `links`, e é por isso que eles
    não estão em `tools` apesar de o portão local os invocar.
    """
    desired = load_desired()

    assert desired.tools is not None
    assert desired.links is not None
    assert not {tool.name for tool in desired.tools} & {link.name for link in desired.links}
