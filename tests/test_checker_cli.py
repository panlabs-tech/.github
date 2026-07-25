"""A interface do checker: read-only, sem flag de aplicação nenhuma.

Não há applier a testar aqui -- só o efeito de formatar e notificar, que este
módulo é.
"""

import json
from pathlib import Path

import pytest

from panlabs import gh
from panlabs.checker.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "checker-observed-sample.json"


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
    clean = tmp_path / "observed.json"
    clean.write_text(
        json.dumps(
            {
                "org": "panlabs-tech",
                "repos": [
                    {
                        "name": "panlabs-tech/skills",
                        "tipo": "skills",
                        "files": ["README.md", "LICENSE"],
                        "has_readme": True,
                        "has_license": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

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
