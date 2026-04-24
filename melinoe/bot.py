import asyncio
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.ext import ApplicationBuilder
from telegram.ext import CommandHandler
from telegram.ext import ContextTypes
from telegram.ext import MessageHandler
from telegram.ext import filters

from melinoe.logger import bot_log
from melinoe.settings import TELEGRAM_BOT_TOKEN
from melinoe.workflows.bookworm import BookwormWorkflow
from melinoe.workflows.bookworm import NotABookCoverError


async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text("Olá! Sou a Melinoe. Como posso ajudar?")


async def log_message(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    user = update.effective_user
    username = user.username if user else "unknown"
    bot_log.info(f"[{username}] {update.message.text}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or not update.message.photo:
        return

    user = update.effective_user
    username = user.username if user else "unknown"
    bot_log.info(f"[{username}] photo received")

    await update.message.reply_text("Foto recebida! Deixa eu analisar a capa do livro...")

    photo = update.message.photo[-1]  # highest resolution
    tg_file = await context.bot.get_file(photo.file_id)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        await tg_file.download_to_drive(tmp_path)
        loop = asyncio.get_running_loop()

        async def _send_progress(text: str) -> None:
            if update.message is not None:
                await update.message.reply_text(text)

        def on_progress(text: str) -> None:
            asyncio.run_coroutine_threadsafe(_send_progress(text), loop)

        result = await asyncio.to_thread(_run_workflow, tmp_path, on_progress)
        reply = _format_result(result)
    except NotABookCoverError:
        reply = (
            "Hmm, não consegui identificar uma capa de livro nessa foto. "
            "Pode enviar uma imagem mais direta da capa frontal, bem iluminada e sem muito desfoque?"
        )
    except Exception as exc:
        bot_log.error(f"BookwormWorkflow failed — {exc}")
        reply = "Desculpe, não consegui identificar o livro. Por favor, tente com uma foto mais nítida."
    finally:
        tmp_path.unlink(missing_ok=True)

    await update.message.reply_text(reply)


def _run_workflow(
    file_path: Path,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    wf = BookwormWorkflow()
    wf.on_progress = on_progress
    return wf.run(file_path)


def _format_result(result: dict[str, Any]) -> str:
    meta: dict[str, Any] = result.get("bibliographic_metadata") or {}
    cover: dict[str, Any] = result.get("cover_analysis") or {}
    confidence: str = result.get("report_confidence", "low")

    title = meta.get("title") or cover.get("title") or "Unknown title"
    author = meta.get("author") or cover.get("author")
    year = meta.get("publication_year")
    publisher = meta.get("publisher")
    pages = meta.get("page_count")
    language = meta.get("language")
    synopsis = meta.get("synopsis")
    genres = meta.get("genres") or []
    awards = meta.get("awards") or []
    ratings: dict[str, Any] = meta.get("ratings") or {}

    _confidence_labels = {"high": "alta", "medium": "média", "low": "baixa"}

    lines: list[str] = [f"*{title}*"]

    if author:
        lines.append(f"por {author}")

    details: list[str] = []
    if year:
        details.append(str(year))
    if publisher:
        details.append(publisher)
    if pages:
        details.append(f"{pages} páginas")
    if language:
        details.append(language)
    if details:
        lines.append(" · ".join(details))

    origin = meta.get("origin")
    if origin:
        lines.append(f"Origem: {origin}")

    if genres:
        lines.append(f"Gêneros: {', '.join(genres)}")

    if synopsis:
        short = synopsis[:400] + ("..." if len(synopsis) > 400 else "")
        lines.append(f"\n{short}")

    if awards:
        lines.append(f"\nPrêmios: {', '.join(awards)}")

    if ratings:
        rating_parts = [f"{source}: {score}" for source, score in ratings.items() if score]
        if rating_parts:
            lines.append(f"Avaliações: {', '.join(rating_parts)}")

    confidence_label = _confidence_labels.get(confidence, confidence)
    lines.append(f"\nConfiança: {confidence_label}")
    return "\n".join(lines)


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))
    app.run_polling()


if __name__ == "__main__":
    main()
