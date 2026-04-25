"""Tests for `icarus catalog-web` command."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from icarus.main import app
from melinoe.workflows.kardo_navalha import ProfessorWorkAlreadyRegisteredError
from melinoe.workflows.skills.execute_web_mentions import WebMention
from melinoe.workflows.skills.execute_web_mentions import WebMentionsResult

runner = CliRunner()


@pytest.fixture()
def web_mention() -> WebMention:
    return WebMention(
        url="https://example.com/poem",
        snippet="Não há relógio que marque\na hora em que a saudade bate.",
        confidence="high",
        source_type="blog",
        discovered_aliases=["Kardo Navalha"],
        discovered_venues=[],
        discovered_years=[2001],
        context_notes="Found on blog.",
    )


@pytest.fixture()
def mentions_result(web_mention: WebMention) -> WebMentionsResult:
    return WebMentionsResult(
        mentions=[web_mention],
        newly_discovered_urls=[],
        urls_visited=["https://example.com/poem"],
        urls_failed=[],
    )


@pytest.fixture()
def catalog_result() -> dict:
    return {
        "detection": {"is_professor_work": True, "confidence": "high", "reason": "scraped", "work_type_hint": None},
        "classification": {"work_type": "poema", "confidence": "medium"},
        "text_analysis": {"work_text": "...", "source_url": "https://example.com/poem"},
        "catalog": {"title": "Trova X", "work_type": "poema", "confidence": "medium"},
        "report_confidence": "medium",
        "output_dir": "/tmp/output/professor/poema-trova-x",
    }


def test_catalog_web_with_url(mentions_result: WebMentionsResult, catalog_result: dict) -> None:
    with (
        patch("icarus.main.ExecuteWebMentionsSkill") as mock_skill_cls,
        patch("icarus.main.KardoNavalhaWorkflow") as mock_wf_cls,
    ):
        mock_skill_cls.return_value.run.return_value = mentions_result
        mock_wf_cls.return_value.run.return_value = catalog_result
        result = runner.invoke(app, ["catalog-web", "https://example.com/poem"])

    assert result.exit_code == 0
    assert '"saved": 1' in result.output


def test_catalog_web_no_url_uses_fallback(catalog_result: dict) -> None:
    with patch("icarus.main.KardoNavalhaWorkflow") as mock_wf_cls:
        mock_wf_cls.return_value.run.return_value = catalog_result
        result = runner.invoke(app, ["catalog-web"])

    assert result.exit_code == 0
    assert '"saved": 1' in result.output
    # ExecuteWebMentionsSkill must NOT have been called
    mock_wf_cls.return_value.run.assert_called_once()
    call_kwargs = mock_wf_cls.return_value.run.call_args.kwargs
    assert call_kwargs["work_text"].startswith("Não há relógio")


def test_catalog_web_force(mentions_result: WebMentionsResult, catalog_result: dict) -> None:
    with (
        patch("icarus.main.ExecuteWebMentionsSkill") as mock_skill_cls,
        patch("icarus.main.KardoNavalhaWorkflow") as mock_wf_cls,
    ):
        mock_skill_cls.return_value.run.return_value = mentions_result
        mock_wf_cls.return_value.run.return_value = catalog_result
        result = runner.invoke(app, ["catalog-web", "https://example.com/poem", "--force"])

    assert result.exit_code == 0
    call_kwargs = mock_wf_cls.return_value.run.call_args.kwargs
    assert call_kwargs["force_update"] is True


def test_catalog_web_skip_already_registered(mentions_result: WebMentionsResult) -> None:
    with (
        patch("icarus.main.ExecuteWebMentionsSkill") as mock_skill_cls,
        patch("icarus.main.KardoNavalhaWorkflow") as mock_wf_cls,
    ):
        mock_skill_cls.return_value.run.return_value = mentions_result
        mock_wf_cls.return_value.run.side_effect = ProfessorWorkAlreadyRegisteredError(
            memory_keys=["x"], title="Trova X"
        )
        result = runner.invoke(app, ["catalog-web", "https://example.com/poem"])

    assert result.exit_code == 1
    assert '"saved": 0' in result.output


def test_catalog_web_no_eligible_mentions() -> None:
    empty_result = WebMentionsResult(
        mentions=[
            WebMention(
                url="https://x.com",
                snippet="short",
                confidence="low",
                source_type="blog",
                discovered_aliases=[],
                discovered_venues=[],
                discovered_years=[],
                context_notes=None,
            )
        ],
        newly_discovered_urls=[],
        urls_visited=["https://x.com"],
        urls_failed=[],
    )

    with patch("icarus.main.ExecuteWebMentionsSkill") as mock_skill_cls:
        mock_skill_cls.return_value.run.return_value = empty_result
        result = runner.invoke(app, ["catalog-web", "https://x.com"])

    assert result.exit_code == 1


def test_catalog_web_fetch_failure_warns(mentions_result: WebMentionsResult, catalog_result: dict) -> None:
    failed_result = WebMentionsResult(
        mentions=mentions_result.mentions,
        newly_discovered_urls=[],
        urls_visited=[],
        urls_failed=["https://example.com/poem"],
    )

    with (
        patch("icarus.main.ExecuteWebMentionsSkill") as mock_skill_cls,
        patch("icarus.main.KardoNavalhaWorkflow") as mock_wf_cls,
    ):
        mock_skill_cls.return_value.run.return_value = failed_result
        mock_wf_cls.return_value.run.return_value = catalog_result
        result = runner.invoke(app, ["catalog-web", "https://example.com/poem"])

    # WARNING goes to stderr — with mix_stderr=True (default) it appears in output
    assert "WARNING" in result.output


def test_catalog_web_output_is_json(mentions_result: WebMentionsResult, catalog_result: dict) -> None:
    split_runner = CliRunner(mix_stderr=False)
    with (
        patch("icarus.main.ExecuteWebMentionsSkill") as mock_skill_cls,
        patch("icarus.main.KardoNavalhaWorkflow") as mock_wf_cls,
    ):
        mock_skill_cls.return_value.run.return_value = mentions_result
        mock_wf_cls.return_value.run.return_value = catalog_result
        result = split_runner.invoke(app, ["catalog-web", "https://example.com/poem"])

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert "saved" in parsed
    assert "results" in parsed
