"""A fronteira do heartbeat com a máquina e com o host.

O que se testa aqui é o que é **nosso**: a forma da consulta, a varredura dos
caches versionados e a leitura do retrato cru. O comportamento do agendador, do
`diskpart` e do próprio WSL não se testa; ele foi verificado por experimento
durante o mapeamento e re-testá-lo seria testar o sistema operacional.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from panlabs.heartbeat import observe
from panlabs.heartbeat.config import Desired, DesiredStep, DropMatching
from panlabs.heartbeat.model import BRANCH_UP
from panlabs.heartbeat.observe import (
    build_observed,
    observed_to_dict,
    scan_leftovers,
    scan_versions,
)

BOOTS = ("-d", "--distribution", "--exec", "-e", "--cd")
KILLS = ("--shutdown", "--terminate", "-t")


# --- a consulta de ramo: inócua por construção --------------------------------


def test_the_wsl_query_never_boots_and_never_shuts_anything_down():
    """A tarefa consulta o estado do WSL sem bootar nada, e nunca o desliga.

    O ciclo completo forçado foi rejeitado porque um desligamento agendado pode
    matar sessão de trabalho no meio, e há repositórios com trabalho não commitado
    morando lá dentro.
    """
    assert set(observe.WSL_QUERY) & set(BOOTS) == set()
    assert set(observe.WSL_QUERY) & set(KILLS) == set()
    assert "--running" in observe.WSL_QUERY


def test_the_host_disk_is_measured_from_the_host_and_not_from_inside():
    """De dentro o `df` reporta centenas de GB que fisicamente não existem."""
    assert observe.HOST_DISK_QUERY[0].endswith(".exe")


# --- os caches versionados ----------------------------------------------------


def make_tree(root: Path, paths: list[str]) -> None:
    for path in paths:
        (root / path).mkdir(parents=True, exist_ok=True)


def test_a_cache_that_versions_at_the_root_is_read_family_by_family(tmp_path: Path):
    make_tree(tmp_path, ["chromium-1161", "chromium-1223", "chromium_headless_shell-1169"])

    found = scan_versions([str(tmp_path)])

    assert [(entry["family"], entry["version"]) for entry in found] == [
        ("chromium", [1161]),
        ("chromium", [1223]),
        ("chromium_headless_shell", [1169]),
    ]


def test_a_cache_that_versions_by_product_carries_the_product_in_the_family(tmp_path: Path):
    """Sem o caminho do produto, `chrome/linux-148` e `shell/linux-127` seriam a mesma família."""
    make_tree(tmp_path, ["chrome/linux-148.0.7778.97", "chrome-headless-shell/linux-127.0.6533.72"])

    found = scan_versions([str(tmp_path)])

    assert [(entry["family"], entry["version"]) for entry in found] == [
        ("chrome-headless-shell/linux", [127, 0, 6533, 72]),
        ("chrome/linux", [148, 0, 7778, 97]),
    ]


def test_the_inside_of_a_revision_is_never_read_as_another_revision(tmp_path: Path):
    """O que mora dentro de uma revisão é o browser, e ali não há versão a comparar."""
    make_tree(tmp_path, ["chromium-1223/chrome-linux-64"])

    found = scan_versions([str(tmp_path)])

    assert [entry["family"] for entry in found] == ["chromium"]


def test_a_directory_that_is_not_a_revision_is_not_a_pruning_candidate(tmp_path: Path):
    make_tree(tmp_path, [".links", "chrome-headless-shell"])

    assert scan_versions([str(tmp_path)]) == []


def test_a_root_that_does_not_exist_is_not_an_error(tmp_path: Path):
    assert scan_versions([str(tmp_path / "nunca-existiu")]) == []


# --- os arquivos órfãos, por forma de nome ------------------------------------


def leftovers_step(root: Path, suffix: str = ".zip") -> Desired:
    return Desired(
        steps=(
            DesiredStep(
                name="zips",
                branch=BRANCH_UP,
                every_days=7,
                alarm="falha",
                why="arquivo de instalação que sobrou",
                drop_matching=DropMatching(root=str(root), suffix=suffix),
            ),
        )
    )


def test_a_leftover_is_found_by_the_shape_of_its_name(tmp_path: Path):
    (tmp_path / "chrome").mkdir()
    (tmp_path / "chrome" / "127-linux64.zip").write_text("x", encoding="utf-8")
    (tmp_path / "chrome" / "README").write_text("x", encoding="utf-8")

    found = scan_leftovers(leftovers_step(tmp_path))

    assert [Path(entry["path"]).name for entry in found] == ["127-linux64.zip"]


def test_a_leftover_scan_never_looks_at_a_root_nobody_declared(tmp_path: Path):
    (tmp_path / "outro.zip").write_text("x", encoding="utf-8")

    assert scan_leftovers(Desired(steps=())) == []


# --- do cru para o tipo -------------------------------------------------------


def test_an_absent_wsl_state_is_unconsulted_and_never_collapses_into_stopped():
    """Colapsar em "parado" mandaria a compactação para cima de um disco vivo."""
    observed = build_observed({"now": "2026-07-25T03:00:00+00:00"})

    assert observed.wsl_running is None
    assert observed.branch is None


def test_a_raw_snapshot_survives_the_round_trip(tmp_path: Path):
    raw = {
        "now": "2026-07-25T03:00:00+00:00",
        "wsl_running": True,
        "host": {"measured": True, "free_bytes": 49_000_000_000, "total_bytes": 490_000_000_000},
        "last_run": "2026-07-24T03:00:00+00:00",
        "marks": [{"step": "npm-cache", "at": "2026-07-18T03:00:00+00:00"}],
        "versions": [
            {
                "root": "/c/ms-playwright",
                "family": "chromium",
                "version": [1161],
                "path": "/c/ms-playwright/chromium-1161",
                "bytes": 800_000_000,
            }
        ],
        "leftovers": [{"root": "/c/puppeteer", "path": "/c/puppeteer/a.zip", "bytes": 200}],
    }

    assert observed_to_dict(build_observed(raw)) == raw


def test_a_run_mark_is_read_from_the_state_directory(tmp_path: Path):
    (tmp_path / observe.MARKS_FILE).write_text(
        json.dumps({"last_run": "2026-07-24T03:00:00+00:00", "steps": {"npm-cache": "x"}}),
        encoding="utf-8",
    )

    assert observe.read_marks(tmp_path)["last_run"] == "2026-07-24T03:00:00+00:00"


def test_a_marks_file_written_by_the_host_with_a_byte_order_mark_is_still_read(tmp_path: Path):
    """Este arquivo tem dois autores, e o do host grava a marca de ordem de bytes.

    Recusá-la faria toda execução parecer o primeiro disparo: a cadência de todos
    os passos zeraria e o alarme de marca velha nunca tocaria. Aconteceu de
    verdade na primeira execução de ponta a ponta.
    """
    (tmp_path / observe.MARKS_FILE).write_text(
        '﻿{"last_run": "2026-07-24T03:00:00+00:00", "steps": {}}', encoding="utf-8"
    )

    assert observe.read_marks(tmp_path)["last_run"] == "2026-07-24T03:00:00+00:00"


def test_a_corrupt_marks_file_reads_as_the_first_trigger_instead_of_exploding(tmp_path: Path):
    """A marca é estado de runtime: um arquivo truncado não pode derrubar a tarefa."""
    (tmp_path / observe.MARKS_FILE).write_text("{ truncado", encoding="utf-8")

    assert observe.read_marks(tmp_path) == {}


def test_an_absent_marks_file_is_the_first_trigger(tmp_path: Path):
    assert observe.read_marks(tmp_path / "vazio") == {}


def test_a_now_that_came_with_the_snapshot_is_the_one_the_planner_uses():
    """A cadência é aritmética sobre o tempo, e o tempo entra como observação."""
    observed = build_observed({"now": "2026-07-25T03:00:00+00:00"})

    assert observed.now == datetime(2026, 7, 25, 3, 0, tzinfo=UTC)
