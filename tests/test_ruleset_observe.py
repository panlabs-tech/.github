"""A observação do ruleset: o que a plataforma recusou a mostrar não vira "nada".

Um repositório privado num plano que não oferece rulesets responde 403 às duas
leituras de proteção, e as duas recusas chegam com o mesmo texto do GitHub. Antes
deste conserto a primeira delas derrubava a corrida inteira, o que tornava o plano
da frota **inobtenível**: pior do que parcial, porque não dizia nada sobre os
outros sete repositórios.

O que estes testes prendem é a metade oposta do risco: que o conserto não vire um
`try/except` que troca o crash por silêncio. "Nenhum ruleset governa a branch" e
"ninguém conseguiu ler os rulesets desta branch" levam a planos opostos, e só o
primeiro pode sair de uma observação.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from panlabs import gh
from panlabs.plan import Unobservable
from panlabs.ruleset.model import RepoState
from panlabs.ruleset.observe import build_observed, fetch_raw, observed_to_dict

FIXTURES = Path(__file__).parent / "fixtures"
FLEET = FIXTURES / "fleet-2026-07-27.json"

DOTFILES = "panlabs-tech/dotfiles"
UPGRADE_403 = (
    "gh: Upgrade to GitHub Pro or make this repository public to enable this feature. (HTTP 403)"
)


def fleet_raw() -> dict[str, Any]:
    return json.loads(FLEET.read_text(encoding="utf-8"))


def repo_named(name: str, raw: dict[str, Any] | None = None) -> RepoState:
    observed = build_observed(raw if raw is not None else fleet_raw())
    return next(repo for repo in observed.repos if repo.name == name)


# --- o retrato cru guarda a recusa, e a corrida continua -----------------------


def fake_org(monkeypatch: pytest.MonkeyPatch, refuse: set[str]) -> None:
    """Uma org de dois repos, um dos quais a plataforma recusa a mostrar."""
    monkeypatch.setattr(gh, "repo_names", lambda _org: ("aberto", "fechado"))

    def api(path: str, **_kwargs: Any) -> Any:
        repo = path.split("/")[2]
        if any(path.endswith(suffix) for suffix in ("/rulesets", "/protection")):
            if repo in refuse:
                raise gh.GhUpgradeRequiredError(UPGRADE_403)
            return [] if path.endswith("/rulesets") else {}
        return {"default_branch": "main", "allow_squash_merge": True}

    monkeypatch.setattr(gh, "api", api)


def test_a_repo_the_platform_refuses_does_not_abort_the_whole_run(
    monkeypatch: pytest.MonkeyPatch,
):
    """A regressão de verdade: hoje um 403 num repo apaga o plano dos outros."""
    fake_org(monkeypatch, refuse={"fechado"})

    raw = fetch_raw("panlabs-tech")

    assert [entry["name"] for entry in raw["repos"]] == [
        "panlabs-tech/aberto",
        "panlabs-tech/fechado",
    ]


def test_the_snapshot_records_what_the_platform_said_instead_of_a_blank(
    monkeypatch: pytest.MonkeyPatch,
):
    """A fixture tem que ser o que a API disse, e ela disse 403 com uma frase dentro."""
    fake_org(monkeypatch, refuse={"fechado"})

    fechado = next(e for e in fetch_raw("panlabs-tech")["repos"] if e["name"].endswith("fechado"))

    assert "Upgrade to GitHub" in fechado["unobservable"]["rulesets"]
    assert "Upgrade to GitHub" in fechado["unobservable"]["classic_protection"]
    assert "rulesets" not in fechado


def test_a_403_that_is_not_about_the_plan_still_aborts(monkeypatch: pytest.MonkeyPatch):
    """Falta de permissão tem conserto pelo operador, e engoli-la esconderia o conserto."""
    monkeypatch.setattr(gh, "repo_names", lambda _org: ("qualquer",))

    def api(path: str, **_kwargs: Any) -> Any:
        if path.endswith("/rulesets"):
            raise gh.GhError("gh: Must have admin rights to Repository. (HTTP 403)")
        return {"default_branch": "main"}

    monkeypatch.setattr(gh, "api", api)

    with pytest.raises(gh.GhError, match="admin rights"):
        fetch_raw("panlabs-tech")


def test_the_settings_of_a_refused_repo_are_still_observed(monkeypatch: pytest.MonkeyPatch):
    """`GET /repos` responde 200 no repo privado: a cegueira é das duas leituras de proteção."""
    fake_org(monkeypatch, refuse={"fechado"})

    fechado = next(e for e in fetch_raw("panlabs-tech")["repos"] if e["name"].endswith("fechado"))

    assert fechado["settings"]["allow_squash_merge"] is True
    assert fechado["default_branch"] == "main"


# --- o estado observado não deixa a recusa passar por resposta -----------------


def test_the_versioned_snapshot_carries_the_private_repo_the_live_org_has():
    """A fixture de 24/07 foi capturada antes de o repo privado existir, e por isso
    537 testes verdes deixaram passar um 403 fatal na frota inteira."""
    assert repo_named(DOTFILES).unobservable()


def test_an_unobservable_ruleset_is_not_an_empty_list_of_rulesets():
    dotfiles = repo_named(DOTFILES)

    assert isinstance(dotfiles.rulesets, Unobservable)
    assert isinstance(dotfiles.classic_protection, Unobservable)


def test_the_unobservable_reason_quotes_the_platform_verbatim():
    """Parafrasear seria escolher qual dos dois 403 aconteceu sem ter como saber."""
    dotfiles = repo_named(DOTFILES)
    assert isinstance(dotfiles.rulesets, Unobservable)

    assert "Upgrade to GitHub" in dotfiles.rulesets.reason


def test_asking_a_refused_repo_which_rulesets_govern_it_raises_instead_of_answering_none():
    """Este é o guarda contra o conserto virar silêncio.

    Devolver tupla vazia seria "nenhum ruleset governa a branch", que é uma
    afirmação sobre o repositório, e ninguém a observou. Um item de plano sairia
    daí mandando criar um ruleset que já pode existir.
    """
    dotfiles = repo_named(DOTFILES)

    with pytest.raises(ValueError, match="não observ"):
        dotfiles.rulesets_governing_default_branch()

    with pytest.raises(ValueError, match="não observ"):
        dotfiles.required_check_contexts()


def test_an_observable_repo_answers_normally():
    """O caminho de sempre continua sendo o caminho de sempre."""
    meta = repo_named("panlabs-tech/.github")

    assert meta.unobservable() == ()
    assert meta.rulesets_governing_default_branch()


def test_a_repo_that_becomes_readable_leaves_the_retention_on_its_own():
    """A idempotência do conserto: nada aqui nomeia repositório nenhum."""
    raw = fleet_raw()
    for entry in raw["repos"]:
        if entry["name"] == DOTFILES:
            entry.pop("unobservable", None)
            entry["rulesets"] = []
            entry["classic_protection"] = None

    dotfiles = repo_named(DOTFILES, raw)

    assert dotfiles.unobservable() == ()
    assert dotfiles.rulesets == ()


def test_the_serialized_state_omits_what_was_not_observed_instead_of_nulling_it():
    """`classic_protection: null` já significa "não existe proteção clássica".

    Reusar esse `null` para "não consegui ler" faria o dump dizer que o repo está
    sem proteção clássica, que é exatamente a afirmação que ninguém pode fazer.
    """
    dump = observed_to_dict(build_observed(fleet_raw()))
    dotfiles = next(entry for entry in dump["repos"] if entry["name"] == DOTFILES)

    assert "rulesets" not in dotfiles
    assert "classic_protection" not in dotfiles
    assert "Upgrade to GitHub" in dotfiles["unobservable"]["rulesets"]


def test_the_serialized_state_survives_json_because_it_is_what_show_observed_prints():
    """O dump vai direto para `json.dumps` no CLI, e `Unobservable` não serializa.

    Um campo de três valores que escape para o dicionário estoura ali, no comando
    que o operador roda para conferir antes de aprovar. O gêmeo de org tem a mesma
    asserção: foi ela que pegou esse estouro uma vez.
    """
    assert json.dumps(observed_to_dict(build_observed(fleet_raw())))
