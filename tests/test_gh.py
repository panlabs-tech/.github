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
"""

import subprocess
from collections.abc import Sequence
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
