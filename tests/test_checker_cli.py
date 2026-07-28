"""A interface do checker: read-only, sem flag de aplicação nenhuma.

Não há applier a testar aqui -- só o efeito de formatar e notificar, que este
módulo é. O que **tem** teste é o código de saída, porque ele deixou de ser
detalhe: é por ele que o passo do heartbeat escolhe em qual canal alarmar, e
`1` significa deriva, e só deriva.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from panlabs import gh
from panlabs.checker.cli import EXIT_CLEAN, EXIT_DRIFT, EXIT_ERROR, main
from panlabs.checker.desired import load_desired

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "checker-observed-sample.json"

SERIES_DECIDED = {"python_series": "3.13", "node_series": "24"}
"""Um valor qualquer para cada série, só para provar que a lista esvazia.

Não são as séries da frota, e não devem ser: decidi-las é ato do operador em
`config/anatomy.json`, e um teste que as cravasse aqui viraria o lugar errado onde
alguém procuraria a decisão.
"""


@pytest.fixture
def forbid_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ler um retrato salvo nunca pode tocar a API: read-only é read-only."""

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("o checker chamou a API mesmo lendo um retrato salvo")

    monkeypatch.setattr(gh, "api", explode)
    monkeypatch.setattr(gh, "repo_names", explode)


def test_running_against_a_saved_snapshot_reaches_no_api_at_all(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    code = main(["--observed", str(SAMPLE)])

    assert code == 1
    assert "3 repo(s) avaliado(s)" in capsys.readouterr().out


def test_the_matrix_the_operator_reads_names_item_scope_and_reason(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    main(["--observed", str(SAMPLE)])

    out = capsys.readouterr().out

    assert "panlabs-tech/tfbox" in out
    assert "readme-exists" in out
    assert "não tem README" in out


def test_a_repo_with_no_drift_and_no_error_yields_exit_zero(
    forbid_api: None, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    """O mesmo retrato de sempre, menos o único defeito que ele carrega.

    Derivado da fixture em vez de montado à mão: com o catálogo cheio, um
    repositório conforme escrito inline neste teste declararia trinta fatos, e o
    dia em que um item novo entrasse ele falharia sem ter nada a dizer sobre a
    interface, que é o que este arquivo testa.
    """
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    for entry in raw["repos"]:
        entry["has_readme"] = True

    clean = tmp_path / "observed.json"
    clean.write_text(json.dumps(raw), encoding="utf-8")

    code = main(["--observed", str(clean)])

    assert code == 0
    assert "Nenhuma deriva ou erro" in capsys.readouterr().out


def test_an_observation_error_outweighs_drift_in_the_exit_code(forbid_api: None, tmp_path: Path):
    unstable = tmp_path / "observed.json"
    unstable.write_text(
        json.dumps(
            {
                "org": "panlabs-tech",
                "repos": [
                    {"name": "panlabs-tech/instavel", "error": "HTTP 401"},
                    {"name": "panlabs-tech/tfbox", "files": [], "has_readme": False},
                ],
            }
        ),
        encoding="utf-8",
    )

    code = main(["--observed", str(unstable)])

    assert code == 2


def test_json_output_is_the_serialized_matrix_and_nothing_else(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    main(["--observed", str(SAMPLE), "--json"])

    payload = json.loads(capsys.readouterr().out)

    assert len(payload["items"]) == 1
    assert {"action", "target", "reason", "payload", "hold"} == set(payload["items"][0])
    assert payload["items"][0]["payload"]["verdict"] == "deriva"


def test_the_serialized_matrix_also_says_what_was_never_asked(
    forbid_api: None, capsys: pytest.CaptureFixture[str]
):
    """A saída humana já dizia isto; a serializada é onde ninguém está lá para inferir.

    `config/anatomy.json` tem três dimensões em `null` hoje, e os itens delas não
    são avaliados. Um consumidor automático lia a matriz, não via linha nenhuma
    sobre licença uniforme nem sobre série de runtime, e concluía conformidade. "Não
    apareceu" e "não foi perguntado" são coisas diferentes, e a segunda precisa de
    quem a diga justamente onde não há humano lendo.
    """
    main(["--observed", str(SAMPLE), "--json"])

    payload = json.loads(capsys.readouterr().out)

    assert set(payload) == {"items", "undecided"}
    assert "license" in payload["undecided"]


def test_a_fully_decided_anatomy_serializes_an_empty_undecided_list(
    forbid_api: None, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    """A chave existe sempre, vazia inclusive: ausência de chave não é dado.

    Um consumidor que precise fazer `if "undecided" in payload` para saber se o
    produtor era velho está lendo a versão do produtor, não a anatomia.
    """
    decided = replace(load_desired(), license="MIT", **SERIES_DECIDED)
    monkeypatch.setattr("panlabs.checker.cli.load_desired", lambda *_a, **_k: decided)

    main(["--observed", str(SAMPLE), "--json"])

    assert json.loads(capsys.readouterr().out)["undecided"] == []


# --- o código de saída: 1 é deriva, e só deriva -------------------------------


def test_a_credential_failure_before_any_matrix_exists_is_an_error_and_never_drift(
    monkeypatch: pytest.MonkeyPatch,
):
    """Este era o disfarce que sobrava: o token expira e a frota inteira "derivou".

    A listagem da org falha antes de qualquer repositório ser observado, então
    não existe matriz nenhuma. Sair com o código de deriva ali seria a mentira
    exata que os dois canais separados existem para impedir.
    """

    def explode(*_args: object, **_kwargs: object) -> object:
        raise gh.GhError("HTTP 401: Bad credentials")

    monkeypatch.setattr(gh, "repo_names", explode)

    assert main([]) == EXIT_ERROR


def test_a_snapshot_that_cannot_be_read_is_an_error_and_never_drift(tmp_path: Path):
    assert main(["--observed", str(tmp_path / "nao-existe.json")]) == EXIT_ERROR


def test_invalid_configuration_data_is_an_error_and_never_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Dado inválido impede a matriz de existir, e o que não existe não derivou."""

    def explode(*_args: object, **_kwargs: object) -> object:
        raise ValueError("tipo desconhecido em config/repo-types.json")

    monkeypatch.setattr(gh, "repo_names", lambda _org: ("x",))
    monkeypatch.setattr("panlabs.checker.observe.load_repo_types", explode)

    assert main([]) == EXIT_ERROR


def test_the_three_exit_codes_are_distinct_because_two_channels_depend_on_it():
    assert len({EXIT_CLEAN, EXIT_DRIFT, EXIT_ERROR}) == 3
