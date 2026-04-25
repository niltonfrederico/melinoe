"""Tests for `icarus reset` command."""

from unittest.mock import MagicMock
from unittest.mock import patch

from typer.testing import CliRunner

import melinoe.settings as settings
from icarus.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Guard: DEBUG=False
# ---------------------------------------------------------------------------


def test_reset_blocked_when_not_debug() -> None:
    with patch.object(settings, "DEBUG", False):
        result = runner.invoke(app, ["reset", "--indexes"])

    assert result.exit_code == 1
    assert "DEBUG=True" in result.output


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


def test_reset_requires_a_flag() -> None:
    with patch.object(settings, "DEBUG", True):
        result = runner.invoke(app, ["reset"])

    assert result.exit_code == 1
    assert "--indexes" in result.output or "specify" in result.output


def test_reset_flags_are_mutually_exclusive() -> None:
    with patch.object(settings, "DEBUG", True):
        result = runner.invoke(app, ["reset", "--indexes", "--storage"])

    assert result.exit_code == 1
    assert "mutually exclusive" in result.output


# ---------------------------------------------------------------------------
# --indexes
# ---------------------------------------------------------------------------


def test_reset_indexes_clears_both_meilisearch_indexes() -> None:
    with (
        patch.object(settings, "DEBUG", True),
        patch("icarus.main.MeilisearchClient") as mock_books,
        patch("icarus.main.NiltonWorksMeilisearchClient") as mock_nilton,
    ):
        result = runner.invoke(app, ["reset", "--indexes"])

    assert result.exit_code == 0
    mock_books.return_value.clear.assert_called_once()
    mock_nilton.return_value.clear.assert_called_once()
    assert "books" in result.output
    assert "nilton_works" in result.output


def test_reset_indexes_does_not_touch_storage() -> None:
    with (
        patch.object(settings, "DEBUG", True),
        patch("icarus.main.MeilisearchClient"),
        patch("icarus.main.NiltonWorksMeilisearchClient"),
        patch("icarus.main.SeaweedFSClient") as mock_sfs,
    ):
        runner.invoke(app, ["reset", "--indexes"])

    mock_sfs.assert_not_called()


def test_reset_indexes_uses_settings() -> None:
    with (
        patch.object(settings, "DEBUG", True),
        patch("icarus.main.MeilisearchClient") as mock_books,
        patch("icarus.main.NiltonWorksMeilisearchClient") as mock_nilton,
    ):
        runner.invoke(app, ["reset", "--indexes"])

    mock_books.assert_called_once_with(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)
    mock_nilton.assert_called_once_with(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)


# ---------------------------------------------------------------------------
# --storage
# ---------------------------------------------------------------------------


def test_reset_storage_deletes_books_and_professor_directories() -> None:
    with (
        patch.object(settings, "DEBUG", True),
        patch("icarus.main.SeaweedFSClient") as mock_sfs_cls,
    ):
        mock_sfs = MagicMock()
        mock_sfs_cls.return_value = mock_sfs
        result = runner.invoke(app, ["reset", "--storage"])

    assert result.exit_code == 0
    calls = [call.args[0] for call in mock_sfs.delete_directory.call_args_list]
    assert "books" in calls
    assert "professor" in calls


def test_reset_storage_does_not_touch_indexes() -> None:
    with (
        patch.object(settings, "DEBUG", True),
        patch("icarus.main.SeaweedFSClient"),
        patch("icarus.main.MeilisearchClient") as mock_books,
        patch("icarus.main.NiltonWorksMeilisearchClient") as mock_nilton,
    ):
        runner.invoke(app, ["reset", "--storage"])

    mock_books.return_value.clear.assert_not_called()
    mock_nilton.return_value.clear.assert_not_called()


def test_reset_storage_uses_settings() -> None:
    with (
        patch.object(settings, "DEBUG", True),
        patch("icarus.main.SeaweedFSClient") as mock_sfs_cls,
    ):
        runner.invoke(app, ["reset", "--storage"])

    expected_public = settings.SEAWEEDFS_PUBLIC_URL or None
    mock_sfs_cls.assert_called_once_with(settings.SEAWEEDFS_FILER_URL, expected_public)


# ---------------------------------------------------------------------------
# --all
# ---------------------------------------------------------------------------


def test_reset_all_clears_indexes_and_storage() -> None:
    with (
        patch.object(settings, "DEBUG", True),
        patch("icarus.main.MeilisearchClient") as mock_books,
        patch("icarus.main.NiltonWorksMeilisearchClient") as mock_nilton,
        patch("icarus.main.SeaweedFSClient") as mock_sfs_cls,
    ):
        mock_sfs = MagicMock()
        mock_sfs_cls.return_value = mock_sfs
        result = runner.invoke(app, ["reset", "--all"])

    assert result.exit_code == 0
    mock_books.return_value.clear.assert_called_once()
    mock_nilton.return_value.clear.assert_called_once()
    assert mock_sfs.delete_directory.call_count == 2
