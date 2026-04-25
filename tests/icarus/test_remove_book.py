"""Tests for `icarus remove-book` command."""

from unittest.mock import patch

from typer.testing import CliRunner

from icarus.main import app

runner = CliRunner()


def test_remove_book_success() -> None:
    with patch("icarus.main.MeilisearchClient") as mock_cls:
        mock_cls.return_value.delete_book.return_value = None
        result = runner.invoke(app, ["remove-book", "abc-123"])

    assert result.exit_code == 0
    assert "Removed: abc-123" in result.output
    mock_cls.return_value.delete_book.assert_called_once_with("abc-123")


def test_remove_book_uses_settings() -> None:
    import melinoe.settings as settings

    with patch("icarus.main.MeilisearchClient") as mock_cls:
        mock_cls.return_value.delete_book.return_value = None
        runner.invoke(app, ["remove-book", "xyz"])

    mock_cls.assert_called_once_with(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)


def test_remove_book_missing_arg() -> None:
    result = runner.invoke(app, ["remove-book"])
    assert result.exit_code != 0


def test_remove_book_propagates_meilisearch_error() -> None:
    with patch("icarus.main.MeilisearchClient") as mock_cls:
        mock_cls.return_value.delete_book.side_effect = RuntimeError("connection refused")
        result = runner.invoke(app, ["remove-book", "bad-id"])

    assert result.exit_code != 0
