"""Tests for `icarus scrape` command."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from icarus.main import app

runner = CliRunner()


@pytest.fixture()
def scrape_result() -> dict:
    return {
        "session_id": "abc123",
        "urls_visited": 5,
        "new_mentions_found": 2,
        "works_saved": 1,
        "profile_enriched": True,
        "new_discoveries": ["Trovador desde 1980"],
        "pending_urls_remaining": 0,
        "summary": "Completed successfully.",
    }


def test_scrape_default_trigger(scrape_result: dict) -> None:
    with patch("icarus.main.SenhorDasHorasMortasWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = scrape_result
        result = runner.invoke(app, ["scrape"])

    assert result.exit_code == 0
    mock_cls.return_value.run.assert_called_once_with(trigger="cron", batch_size=10)


def test_scrape_cron_trigger(scrape_result: dict) -> None:
    with patch("icarus.main.SenhorDasHorasMortasWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = scrape_result
        result = runner.invoke(app, ["scrape", "--trigger", "cron"])

    assert result.exit_code == 0
    mock_cls.return_value.run.assert_called_once_with(trigger="cron", batch_size=10)


def test_scrape_new_work_trigger(scrape_result: dict) -> None:
    with patch("icarus.main.SenhorDasHorasMortasWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = scrape_result
        result = runner.invoke(app, ["scrape", "--trigger", "new_work"])

    assert result.exit_code == 0
    mock_cls.return_value.run.assert_called_once_with(trigger="new_work", batch_size=10)


def test_scrape_custom_batch_size(scrape_result: dict) -> None:
    with patch("icarus.main.SenhorDasHorasMortasWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = scrape_result
        result = runner.invoke(app, ["scrape", "--batch-size", "25"])

    assert result.exit_code == 0
    mock_cls.return_value.run.assert_called_once_with(trigger="cron", batch_size=25)


def test_scrape_invalid_trigger() -> None:
    with patch("icarus.main.SenhorDasHorasMortasWorkflow") as mock_cls:
        result = runner.invoke(app, ["scrape", "--trigger", "invalid"])

    assert result.exit_code == 1
    mock_cls.return_value.run.assert_not_called()


def test_scrape_output_is_json(scrape_result: dict) -> None:
    with patch("icarus.main.SenhorDasHorasMortasWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = scrape_result
        result = runner.invoke(app, ["scrape"])

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["session_id"] == "abc123"
    assert parsed["works_saved"] == 1
