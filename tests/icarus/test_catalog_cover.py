"""Tests for `icarus catalog-cover` command."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from icarus.main import app
from melinoe.workflows.kardo_navalha import ProfessorWorkAlreadyRegisteredError

runner = CliRunner()


@pytest.fixture()
def cover_image(tmp_path: Path) -> Path:
    f = tmp_path / "cover.jpg"
    f.write_bytes(b"fake-image")
    return f


@pytest.fixture()
def catalog_result() -> dict:
    return {
        "detection": {"is_professor_work": True, "confidence": "high", "reason": "ok", "work_type_hint": "trova"},
        "classification": {"work_type": "trova", "confidence": "high"},
        "cover_analysis": {"title": "Trova X", "author": "Nilton Manoel", "confidence": "high"},
        "catalog": {"title": "Trova X", "work_type": "trova", "confidence": "high"},
        "report_confidence": "high",
        "output_dir": "/tmp/output/professor/trova-x",
        "cover_url": "http://example.com/cover.jpg",
    }


def test_catalog_cover_success(cover_image: Path, catalog_result: dict) -> None:
    with patch("icarus.main.KardoNavalhaWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = catalog_result
        result = runner.invoke(app, ["catalog-cover", str(cover_image)])

    assert result.exit_code == 0
    assert '"report_confidence": "high"' in result.output
    mock_cls.return_value.run.assert_called_once_with(file_path=cover_image, force_update=False)


def test_catalog_cover_force(cover_image: Path, catalog_result: dict) -> None:
    with patch("icarus.main.KardoNavalhaWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = catalog_result
        result = runner.invoke(app, ["catalog-cover", str(cover_image), "--force"])

    assert result.exit_code == 0
    mock_cls.return_value.run.assert_called_once_with(file_path=cover_image, force_update=True)


def test_catalog_cover_already_registered(cover_image: Path) -> None:
    with patch("icarus.main.KardoNavalhaWorkflow") as mock_cls:
        mock_cls.return_value.run.side_effect = ProfessorWorkAlreadyRegisteredError(
            memory_keys=["professor-trova-x"], title="Trova X"
        )
        result = runner.invoke(app, ["catalog-cover", str(cover_image)])

    assert result.exit_code == 2
    assert "Already registered" in result.output
    assert "'Trova X'" in result.output


def test_catalog_cover_output_is_json(cover_image: Path, catalog_result: dict) -> None:
    with patch("icarus.main.KardoNavalhaWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = catalog_result
        result = runner.invoke(app, ["catalog-cover", str(cover_image)])

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["report_confidence"] == "high"


def test_catalog_cover_missing_arg() -> None:
    result = runner.invoke(app, ["catalog-cover"])
    assert result.exit_code != 0
