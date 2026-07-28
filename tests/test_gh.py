"""O adaptador do `gh`: qual falha da plataforma é resposta, e qual é erro.

Um 403 não é um só. "Este plano não oferece rulesets em repositório privado" é
uma resposta sobre o que a plataforma **mostra**, e some quando o repo vira
público. "Eleve o token" é falta de permissão, e some quando o operador eleva o
escopo. Os dois chegam com o mesmo código HTTP, e confundi-los faria o motivo
escrito no plano mentir em metade dos casos.

A distinção mora aqui porque este é o único lugar que vê o que a plataforma
disse. Ela é **fail-closed**: só o texto que o GitHub usa para restrição de
plano vira resposta, e todo o resto continua sendo erro alto. Se o GitHub mudar
esse texto, o conserto degrada para o erro fatal de hoje, que ninguém deixa de
notar. Nunca para o silêncio.

A segunda coisa que mora aqui é **onde** o `gh` está. Ela parece detalhe de
ambiente e não é: quem invoca este adaptador sem terminal (a tarefa agendada do
host, um cron, um serviço) roda com o PATH mínimo do sistema, e nome nu resolve
no terminal e falha lá. Foi assim que o único detector automático de deriva da
org passou a existência inteira sem produzir uma matriz.
"""

import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from panlabs import gh

PLAN_403 = (
    "gh: Upgrade to GitHub Pro or make this repository public to enable this feature. (HTTP 403)"
)
PERMISSION_403 = "gh: Must have admin rights to Repository. (HTTP 403)"


def fake_gh(monkeypatch: pytest.MonkeyPatch, *, returncode: int, stderr: str) -> None:
    def run(args: Sequence[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(args), returncode, "", stderr)

    monkeypatch.setattr("panlabs.gh.subprocess.run", run)


def test_the_403_of_plan_restriction_is_its_own_kind_of_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    """Nenhum token conserta este: o repo é privado num plano que não oferece o recurso."""
    fake_gh(monkeypatch, returncode=1, stderr=PLAN_403)

    with pytest.raises(gh.GhUpgradeRequiredError) as caught:
        gh.api("repos/panlabs-tech/dotfiles/rulesets")

    assert "Upgrade to GitHub" in str(caught.value)


def test_a_403_of_missing_permission_stays_a_plain_error(monkeypatch: pytest.MonkeyPatch):
    """Este o operador conserta elevando o escopo, e ele não pode virar retenção."""
    fake_gh(monkeypatch, returncode=1, stderr=PERMISSION_403)

    with pytest.raises(gh.GhError) as caught:
        gh.api("repos/panlabs-tech/dotfiles/rulesets")

    assert not isinstance(caught.value, gh.GhUpgradeRequiredError)


def test_the_upgrade_failure_is_still_a_gh_error(monkeypatch: pytest.MonkeyPatch):
    """Quem só sabe capturar `GhError` continua capturando este, e para de graça."""
    fake_gh(monkeypatch, returncode=1, stderr=PLAN_403)

    with pytest.raises(gh.GhError):
        gh.api("repos/panlabs-tech/dotfiles/rulesets")


def test_a_404_is_still_not_found(monkeypatch: pytest.MonkeyPatch):
    fake_gh(monkeypatch, returncode=1, stderr="gh: Not Found (HTTP 404)")

    with pytest.raises(gh.GhNotFoundError):
        gh.api("repos/panlabs-tech/dotfiles/vulnerability-alerts")


# --- onde o `gh` está, para quem roda sem terminal ----------------------------


def spy_argv(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Guarda o argv que chegou ao subprocesso, que é o que este bloco mede."""
    seen: list[list[str]] = []

    def run(args: Sequence[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append(list(args))
        return subprocess.CompletedProcess(list(args), 0, "{}", "")

    monkeypatch.setattr("panlabs.gh.subprocess.run", run)
    return seen


def plant_gh(directory: Path) -> Path:
    """Um `gh` executável num diretório, como o instalador por usuário deixaria."""
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / "gh"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary


def test_the_binary_found_on_the_path_is_the_one_that_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Quem tem PATH bom continua mandando: a busca de fallback não sequestra nada."""
    on_path = plant_gh(tmp_path / "usr-bin")
    monkeypatch.setattr("panlabs.gh.shutil.which", lambda _name: str(on_path))
    seen = spy_argv(monkeypatch)

    gh.api("repos/panlabs-tech/.github")

    assert seen[0][0] == str(on_path)


def test_the_user_install_is_found_when_the_path_is_the_bare_system_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """O caso vivo: subprocesso não interativo, sem rc, sem `~/.local/bin` no PATH.

    A tarefa agendada do host roda o passo do heartbeat assim, e é por isso que
    `anatomy-checker` nunca produziu matriz nenhuma: o `gh` existia, e o nome nu
    não o alcançava.
    """
    home = tmp_path / "home"
    planted = plant_gh(home / ".local" / "bin")
    monkeypatch.setattr("panlabs.gh.shutil.which", lambda _name: None)
    monkeypatch.setenv("HOME", str(home))
    seen = spy_argv(monkeypatch)

    gh.api("repos/panlabs-tech/.github")

    assert seen[0][0] == str(planted)


def test_a_directory_named_gh_is_not_mistaken_for_the_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Existir não basta: o que se procura é um executável, e diretório não é um."""
    home = tmp_path / "home"
    (home / ".local" / "bin" / "gh").mkdir(parents=True)
    monkeypatch.setattr("panlabs.gh.shutil.which", lambda _name: None)
    monkeypatch.setenv("HOME", str(home))
    fake_gh(monkeypatch, returncode=0, stderr="")

    monkeypatch.setattr(
        "panlabs.gh.subprocess.run",
        lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError("gh")),
    )

    with pytest.raises(gh.GhError):
        gh.api("repos/panlabs-tech/.github")


def test_the_absent_gh_says_where_it_looked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """A degradação é barulhenta e acionável, nunca silenciosa.

    Um `gh` que de fato não existe continua sendo erro alto, e a mensagem passa a
    dizer onde se procurou: sem isso o operador lê "não está no PATH" numa máquina
    em que `command -v gh` responde, e vai procurar o defeito no lugar errado.
    """
    monkeypatch.setattr("panlabs.gh.shutil.which", lambda _name: None)
    monkeypatch.setenv("HOME", str(tmp_path / "vazio"))

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise FileNotFoundError("gh")

    monkeypatch.setattr("panlabs.gh.subprocess.run", explode)

    with pytest.raises(gh.GhError) as caught:
        gh.api("repos/panlabs-tech/.github")

    assert gh.USER_BIN_DIRS[0] in str(caught.value)


def test_the_fallback_dirs_are_the_ones_this_machine_installs_into():
    """O dado que governa o equipamento da máquina e esta lista são o mesmo lugar.

    `config/machine.json` declara `bin_dir` como o diretório de binário de usuário,
    e a busca aqui precisa cobri-lo. Não é o adaptador que lê aquele arquivo (ele
    roda em CI e em máquina nenhuma também), mas divergir dele traria de volta
    exatamente a falha que este bloco existe para fechar.
    """
    machine = Path(__file__).resolve().parents[1] / "config" / "machine.json"
    import json

    bin_dir = json.loads(machine.read_text(encoding="utf-8"))["bin_dir"]

    assert bin_dir in gh.USER_BIN_DIRS


def test_the_planted_binary_is_only_taken_when_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Arquivo sem bit de execução é lixo com o nome certo, e não o `gh`."""
    home = tmp_path / "home"
    directory = home / ".local" / "bin"
    directory.mkdir(parents=True)
    (directory / "gh").write_text("nao sou executavel\n", encoding="utf-8")
    monkeypatch.setattr("panlabs.gh.shutil.which", lambda _name: None)
    monkeypatch.setenv("HOME", str(home))

    assert not os.access(directory / "gh", os.X_OK)
    assert gh.binary() == "gh"
