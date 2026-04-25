"""Tests for `icarus book` command."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from icarus.main import app
from melinoe.workflows.bookworm import BookAlreadyRegisteredError
from melinoe.workflows.bookworm import NotABookCoverError

runner = CliRunner()


@pytest.fixture()
def cover_image(tmp_path: Path) -> Path:
    f = tmp_path / "cover.jpg"
    f.write_bytes(b"fake-image")
    return f


@pytest.fixture()
def title_page_image(tmp_path: Path) -> Path:
    f = tmp_path / "title.jpg"
    f.write_bytes(b"fake-image")
    return f


@pytest.fixture()
def book_result() -> dict:
    return {
        "cover_analysis": {"title": "Foo", "author": "Bar", "confidence": "high"},
        "title_page_analysis": None,
        "bibliographic_metadata": {"title": "Foo", "author": "Bar", "isbn_13": None},
        "report_confidence": "high",
        "notes": None,
        "output_dir": "/tmp/output/foo",
        "cover_url": "http://example.com/cover.jpg",
    }


def test_book_success(cover_image: Path, book_result: dict) -> None:
    with patch("icarus.main.BookwormWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = book_result
        result = runner.invoke(app, ["book", str(cover_image)])

    assert result.exit_code == 0
    assert '"report_confidence": "high"' in result.output
    mock_cls.return_value.run.assert_called_once_with(cover_image, title_page_path=None, force_update=False)


def test_book_with_title_page(cover_image: Path, title_page_image: Path, book_result: dict) -> None:
    with patch("icarus.main.BookwormWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = book_result
        result = runner.invoke(app, ["book", str(cover_image), "--title-page", str(title_page_image)])

    assert result.exit_code == 0
    mock_cls.return_value.run.assert_called_once_with(cover_image, title_page_path=title_page_image, force_update=False)


def test_book_force_flag(cover_image: Path, book_result: dict) -> None:
    with patch("icarus.main.BookwormWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = book_result
        result = runner.invoke(app, ["book", str(cover_image), "--force"])

    assert result.exit_code == 0
    mock_cls.return_value.run.assert_called_once_with(cover_image, title_page_path=None, force_update=True)


def test_book_not_a_cover(cover_image: Path) -> None:
    with patch("icarus.main.BookwormWorkflow") as mock_cls:
        mock_cls.return_value.run.side_effect = NotABookCoverError("blurry image")
        result = runner.invoke(app, ["book", str(cover_image)])

    assert result.exit_code == 1
    assert "not a book cover" in result.output


def test_book_already_registered(cover_image: Path) -> None:
    with patch("icarus.main.BookwormWorkflow") as mock_cls:
        mock_cls.return_value.run.side_effect = BookAlreadyRegisteredError(
            memory_keys=["foo-bar"], title="Foo", author="Bar"
        )
        result = runner.invoke(app, ["book", str(cover_image)])

    assert result.exit_code == 2
    assert "Already registered" in result.output
    assert "'Foo'" in result.output


def test_book_already_registered_force_skips_error(cover_image: Path, book_result: dict) -> None:
    with patch("icarus.main.BookwormWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = book_result
        result = runner.invoke(app, ["book", str(cover_image), "--force"])

    assert result.exit_code == 0


def test_book_output_is_json(cover_image: Path, book_result: dict) -> None:
    with patch("icarus.main.BookwormWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = book_result
        result = runner.invoke(app, ["book", str(cover_image)])

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["report_confidence"] == "high"


def test_book_missing_cover_arg() -> None:
    result = runner.invoke(app, ["book"])
    assert result.exit_code != 0


def test_book_nonexistent_file() -> None:
    result = runner.invoke(app, ["book", "/does/not/exist.jpg"])
    # Typer validates Path existence by default only if exists=True is set;
    # the workflow itself will raise — exit code comes from the workflow exception
    assert result.exit_code
    assert result.exit_code != 0  # invocation must not crash the runner


def test_book_progress_on_stderr(cover_image: Path, book_result: dict) -> None:

    split_runner = CliRunner(mix_stderr=False)
    with patch("icarus.main.BookwormWorkflow") as mock_cls:
        mock_cls.return_value.run.return_value = book_result
        result = split_runner.invoke(app, ["book", str(cover_image)])

    assert result.exit_code == 0
    # stdout is pure JSON, no progress noise
    json.loads(result.stdout)
