"""Icarus — Melinoe CLI entry point."""

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

import melinoe.settings as settings
from melinoe.clients.meilisearch import MeilisearchClient
from melinoe.clients.meilisearch import NiltonWorksMeilisearchClient
from melinoe.clients.seaweedfs import SeaweedFSClient
from melinoe.workflows.bookworm import BookAlreadyRegisteredError
from melinoe.workflows.bookworm import BookwormWorkflow
from melinoe.workflows.bookworm import NotABookCoverError
from melinoe.workflows.kardo_navalha import KardoNavalhaWorkflow
from melinoe.workflows.kardo_navalha import ProfessorWorkAlreadyRegisteredError
from melinoe.workflows.senhor_das_horas_mortas import SenhorDasHorasMortasWorkflow
from melinoe.workflows.skills.enrich_professor_profile import EnrichProfessorProfileSkill
from melinoe.workflows.skills.execute_web_mentions import ExecuteWebMentionsSkill
from melinoe.workflows.skills.execute_web_mentions import WebMention
from melinoe.workflows.skills.execute_web_mentions import WebMentionsResult
from melinoe.workflows.skills.load_scraping_state import ScrapingState
from melinoe.workflows.skills.plan_scraping import ScrapingPlan

app = typer.Typer(pretty_exceptions_enable=False)

_FALLBACK_SNIPPET = """\
Não há relógio que marque
a hora em que a saudade bate,
ela chega como a tarde
quando o sol a si se abate.

— Nilton Manoel (Kardo Navalha)
"""

_VALID_TRIGGERS = ("cron", "new_work")


def _print_result(result: dict) -> None:  # type: ignore[type-arg]
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


@app.command()
def book(
    cover_path: Annotated[Path, typer.Argument(help="Path to the book cover image file")],
    title_page: Annotated[Path | None, typer.Option("--title-page", help="Path to the title page image")] = None,
    force: Annotated[bool, typer.Option("--force", help="Re-register even if already in memory")] = False,
) -> None:
    """Analyze a book cover and register it in memory and Meilisearch."""
    wf = BookwormWorkflow()
    try:
        result = wf.run(cover_path, title_page_path=title_page, force_update=force)
    except NotABookCoverError as exc:
        typer.echo(f"Error: not a book cover — {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except BookAlreadyRegisteredError as exc:
        typer.echo(
            f"Already registered: {exc.title!r} by {exc.author!r} (keys: {exc.memory_keys})",
            err=True,
        )
        raise typer.Exit(code=2) from exc
    _print_result(result)


@app.command()
def catalog_cover(
    cover_path: Annotated[Path, typer.Argument(help="Path to the professor's work cover image")],
    force: Annotated[bool, typer.Option("--force", help="Re-catalog even if already in memory")] = False,
) -> None:
    """Catalog a cover image as a work by Nilton Manoel (O Professor)."""
    wf = KardoNavalhaWorkflow()
    try:
        result = wf.run(file_path=cover_path, force_update=force)
    except ProfessorWorkAlreadyRegisteredError as exc:
        typer.echo(f"Already registered: {exc.title!r} (keys: {exc.memory_keys})", err=True)
        raise typer.Exit(code=2) from exc
    _print_result(result)


@app.command()
def catalog_web(
    url: Annotated[str | None, typer.Argument(help="URL of a page containing a work by Nilton Manoel")] = None,
    force: Annotated[bool, typer.Option("--force", help="Re-catalog even if already in memory")] = False,
) -> None:
    """Fetch a URL, extract mentions of Nilton Manoel, and catalog any found works."""
    if url is not None:
        typer.echo(f"Fetching {url} …", err=True)
        skill = ExecuteWebMentionsSkill()
        plan = ScrapingPlan(next_urls=[url], search_queries=[], planning_notes="")
        state = ScrapingState(
            visited_urls=[],
            pending_urls=[url],
            found_mentions=[],
            stats={"total_mentions": 0, "total_urls_visited": 0, "total_sessions": 0},
            session_count=0,
            last_new_mention_at=None,
        )
        mentions_result: WebMentionsResult = skill.run(plan=plan, state=state)
        if mentions_result.urls_failed:
            typer.echo(f"WARNING: failed to fetch {url}", err=True)
        eligible = [
            m for m in mentions_result.mentions if m.confidence in ("high", "medium") and len(m.snippet or "") >= 30
        ]
        typer.echo(f"Found {len(mentions_result.mentions)} mention(s), {len(eligible)} eligible.", err=True)
    else:
        typer.echo("No URL provided — using synthetic fallback snippet.", err=True)
        eligible = [
            WebMention(
                url="manual://test-senhor-save",
                snippet=_FALLBACK_SNIPPET,
                confidence="high",
                source_type="blog",
                discovered_aliases=["Kardo Navalha"],
                discovered_venues=[],
                discovered_years=[],
                context_notes="Synthetic test mention.",
            )
        ]

    if not eligible:
        typer.echo("No eligible mentions to catalog.", err=True)
        raise typer.Exit(code=1)

    saved = 0
    results: list[dict] = []  # type: ignore[type-arg]
    wf = KardoNavalhaWorkflow()
    for mention in eligible:
        typer.echo(f"Cataloging snippet from {mention.url} (confidence={mention.confidence}) …", err=True)
        try:
            result = wf.run(work_text=mention.snippet, mention_metadata=asdict(mention), force_update=force)
            saved += 1
            results.append(result)
            typer.echo(f"  → {result.get('output_dir')}", err=True)
        except ProfessorWorkAlreadyRegisteredError as exc:
            typer.echo(f"  SKIP — already registered: {exc.title!r}", err=True)

    typer.echo(f"\n{'OK' if saved else 'FAIL'} — {saved} work(s) saved.", err=True)
    _print_result({"saved": saved, "results": results})
    if not saved:
        raise typer.Exit(code=1)


@app.command()
def scrape(
    trigger: Annotated[str, typer.Option("--trigger", help="Trigger type: cron or new_work")] = "cron",
    batch_size: Annotated[int, typer.Option("--batch-size", help="URLs to process per iteration")] = 10,
) -> None:
    """Run the autonomous web scraper (SenhorDasHorasMortasWorkflow)."""
    if trigger not in _VALID_TRIGGERS:
        typer.echo(f"Error: --trigger must be one of {_VALID_TRIGGERS}", err=True)
        raise typer.Exit(code=1)
    wf = SenhorDasHorasMortasWorkflow()
    result = wf.run(trigger=trigger, batch_size=batch_size)
    _print_result(result)


@app.command()
def enrich(
    file: Annotated[Path | None, typer.Argument(help="Text file with information. Omit to read from stdin.")] = None,
    source: Annotated[str, typer.Option("--source", help="Label for the information source")] = "family_memory",
    url: Annotated[
        str, typer.Option("--url", help="URL or identifier to associate with this information")
    ] = "manual://family-input",
) -> None:
    """Enrich the Professor's profile with manually provided information."""
    if file is not None:
        text = file.read_text().strip()
    else:
        if sys.stdin.isatty():
            typer.echo("Enter information about Nilton Manoel (Ctrl+D when done):", err=True)
        text = sys.stdin.read().strip()

    if not text:
        typer.echo("Error: no input text provided.", err=True)
        raise typer.Exit(code=1)

    mention = WebMention(
        url=url,
        snippet=text,
        confidence="high",
        source_type=source,
        discovered_aliases=[],
        discovered_venues=[],
        discovered_years=[],
        context_notes="Provided manually by family member — treat as high-confidence primary source.",
        article_text=text,
    )
    mentions_result = WebMentionsResult(
        mentions=[mention],
        newly_discovered_urls=[],
        urls_visited=[url],
        urls_failed=[],
    )

    skill = EnrichProfessorProfileSkill()
    result = skill.run(mentions_result=mentions_result)

    if result.profile_updated:
        typer.echo("Profile updated successfully.", err=True)
        for discovery in result.new_discoveries:
            typer.echo(f"  + {discovery}", err=True)
    else:
        typer.echo("No changes made to profile.", err=True)
    _print_result({"profile_updated": result.profile_updated, "new_discoveries": result.new_discoveries})


@app.command()
def remove_book(
    book_id: Annotated[str, typer.Argument(help="Book document ID in Meilisearch")],
) -> None:
    """Remove a book from Meilisearch by its ID."""
    client = MeilisearchClient(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)
    client.delete_book(book_id)
    typer.echo(f"Removed: {book_id}")


@app.command()
def reset(
    indexes: Annotated[bool, typer.Option("--indexes", help="Clear all Meilisearch indexes")] = False,
    storage: Annotated[bool, typer.Option("--storage", help="Delete all SeaweedFS files")] = False,
    all_: Annotated[bool, typer.Option("--all", help="Clear indexes and storage")] = False,
) -> None:
    """Wipe Meilisearch indexes and/or SeaweedFS storage. Only available when DEBUG=True."""
    if not settings.DEBUG:
        typer.echo("Error: reset is only available when DEBUG=True.", err=True)
        raise typer.Exit(code=1)

    flags_set = sum([indexes, storage, all_])
    if flags_set == 0:
        typer.echo("Error: specify one of --indexes, --storage, or --all.", err=True)
        raise typer.Exit(code=1)
    if flags_set > 1:
        typer.echo("Error: --indexes, --storage, and --all are mutually exclusive.", err=True)
        raise typer.Exit(code=1)

    do_indexes = indexes or all_
    do_storage = storage or all_

    if do_indexes:
        books_client = MeilisearchClient(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)
        books_client.clear()
        typer.echo("Cleared index: books")

        nilton_client = NiltonWorksMeilisearchClient(settings.MEILISEARCH_URL, settings.MEILISEARCH_API_KEY)
        nilton_client.clear()
        typer.echo("Cleared index: nilton_works")

    if do_storage:
        sfs = SeaweedFSClient(settings.SEAWEEDFS_FILER_URL, settings.SEAWEEDFS_PUBLIC_URL or None)
        for directory in ("books", "professor"):
            sfs.delete_directory(directory)
            typer.echo(f"Deleted storage directory: /{directory}")


if __name__ == "__main__":
    app()
