"""Tests for `icarus enrich` command."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from icarus.main import app

runner = CliRunner()


@pytest.fixture()
def enrichment_result():
    from melinoe.workflows.skills.enrich_professor_profile import ProfileEnrichmentResult

    return ProfileEnrichmentResult(profile_updated=True, new_discoveries=["Trovador desde 1980"])


@pytest.fixture()
def no_update_result():
    from melinoe.workflows.skills.enrich_professor_profile import ProfileEnrichmentResult

    return ProfileEnrichmentResult(profile_updated=False, new_discoveries=[])


@pytest.fixture()
def text_file(tmp_path: Path) -> Path:
    f = tmp_path / "notes.txt"
    f.write_text("Nilton Manoel foi homenageado na Câmara Municipal em 2003.")
    return f


def test_enrich_from_file(text_file: Path, enrichment_result) -> None:
    with patch("icarus.main.EnrichProfessorProfileSkill") as mock_cls:
        mock_cls.return_value.run.return_value = enrichment_result
        result = runner.invoke(app, ["enrich", str(text_file)])

    assert result.exit_code == 0
    assert "Profile updated" in result.output
    call_kwargs = mock_cls.return_value.run.call_args.kwargs
    mentions_result = call_kwargs["mentions_result"]
    assert len(mentions_result.mentions) == 1
    assert "Câmara Municipal" in mentions_result.mentions[0].snippet


def test_enrich_from_stdin(enrichment_result) -> None:
    with patch("icarus.main.EnrichProfessorProfileSkill") as mock_cls:
        mock_cls.return_value.run.return_value = enrichment_result
        result = runner.invoke(app, ["enrich"], input="Nilton Manoel ganhou o jogo floral de 1998.")

    assert result.exit_code == 0
    call_kwargs = mock_cls.return_value.run.call_args.kwargs
    assert "jogo floral" in call_kwargs["mentions_result"].mentions[0].snippet


def test_enrich_custom_source(text_file: Path, enrichment_result) -> None:
    with patch("icarus.main.EnrichProfessorProfileSkill") as mock_cls:
        mock_cls.return_value.run.return_value = enrichment_result
        result = runner.invoke(app, ["enrich", str(text_file), "--source", "depoimento_familiar"])

    assert result.exit_code == 0
    call_kwargs = mock_cls.return_value.run.call_args.kwargs
    assert call_kwargs["mentions_result"].mentions[0].source_type == "depoimento_familiar"


def test_enrich_custom_url(text_file: Path, enrichment_result) -> None:
    with patch("icarus.main.EnrichProfessorProfileSkill") as mock_cls:
        mock_cls.return_value.run.return_value = enrichment_result
        result = runner.invoke(app, ["enrich", str(text_file), "--url", "manual://family-2024"])

    assert result.exit_code == 0
    call_kwargs = mock_cls.return_value.run.call_args.kwargs
    assert call_kwargs["mentions_result"].mentions[0].url == "manual://family-2024"


def test_enrich_no_update(text_file: Path, no_update_result) -> None:
    with patch("icarus.main.EnrichProfessorProfileSkill") as mock_cls:
        mock_cls.return_value.run.return_value = no_update_result
        result = runner.invoke(app, ["enrich", str(text_file)])

    assert result.exit_code == 0
    assert "No changes" in result.output


def test_enrich_empty_input_exits() -> None:
    with patch("icarus.main.EnrichProfessorProfileSkill"):
        result = runner.invoke(app, ["enrich"], input="")

    assert result.exit_code == 1


def test_enrich_article_text_mirrors_snippet(text_file: Path, enrichment_result) -> None:
    with patch("icarus.main.EnrichProfessorProfileSkill") as mock_cls:
        mock_cls.return_value.run.return_value = enrichment_result
        runner.invoke(app, ["enrich", str(text_file)])

    call_kwargs = mock_cls.return_value.run.call_args.kwargs
    mention = call_kwargs["mentions_result"].mentions[0]
    assert mention.article_text == mention.snippet


def test_enrich_output_is_json(text_file: Path, enrichment_result) -> None:
    split_runner = CliRunner(mix_stderr=False)
    with patch("icarus.main.EnrichProfessorProfileSkill") as mock_cls:
        mock_cls.return_value.run.return_value = enrichment_result
        result = split_runner.invoke(app, ["enrich", str(text_file)])

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["profile_updated"] is True
    assert parsed["new_discoveries"] == ["Trovador desde 1980"]


def test_enrich_mentions_confidence_is_high(text_file: Path, enrichment_result) -> None:
    with patch("icarus.main.EnrichProfessorProfileSkill") as mock_cls:
        mock_cls.return_value.run.return_value = enrichment_result
        runner.invoke(app, ["enrich", str(text_file)])

    call_kwargs = mock_cls.return_value.run.call_args.kwargs
    assert call_kwargs["mentions_result"].mentions[0].confidence == "high"
