import asyncio
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import ApplicationBuilder
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ContextTypes
from telegram.ext import ConversationHandler
from telegram.ext import MessageHandler
from telegram.ext import filters

from melinoe.logger import bot_log
from melinoe.settings import TELEGRAM_BOT_TOKEN
from melinoe.workflows.bookworm import BookwormWorkflow
from melinoe.workflows.bookworm import NotABookCoverError

# Conversation state
_WAITING_TITLE_PAGE = 1
# user_data key where the cover temp path is stored between steps
_COVER_PATH_KEY = "cover_tmp_path"


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


async def handle_cover_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1: receive cover photo, validate it, then ask for title page."""
    if update.message is None or not update.message.photo:
        return ConversationHandler.END

    user = update.effective_user
    username = user.username if user else "unknown"
    bot_log.info(f"[{username}] cover photo received")

    await update.message.reply_text("Foto recebida! Deixa eu verificar se é uma capa de livro...")

    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        await tg_file.download_to_drive(tmp_path)
    except Exception as exc:
        bot_log.error(f"Failed to download cover — {exc}")
        tmp_path.unlink(missing_ok=True)
        await update.message.reply_text("Não consegui baixar a foto. Por favor, tente novamente.")
        return ConversationHandler.END

    # Store path for use in the next step; previous temp file (if any) is cleaned up
    old_cover: str | None = context.user_data.get(_COVER_PATH_KEY)  # type: ignore[union-attr]
    if old_cover:
        Path(old_cover).unlink(missing_ok=True)
    context.user_data[_COVER_PATH_KEY] = str(tmp_path)  # type: ignore[index]

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Não tem folha de rosto", callback_data="no_title_page")]])
    await update.message.reply_text(
        "Tem a folha de rosto do livro? Envie uma foto ou indique abaixo se não tiver.",
        reply_markup=keyboard,
    )
    return _WAITING_TITLE_PAGE


async def handle_title_page_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2a: user sent a title page photo — run workflow with both images."""
    if update.message is None or not update.message.photo:
        return _WAITING_TITLE_PAGE

    cover_path_str: str | None = context.user_data.get(_COVER_PATH_KEY)  # type: ignore[union-attr]
    if not cover_path_str:
        await update.message.reply_text("Algo deu errado. Por favor, envie a capa do livro novamente.")
        return ConversationHandler.END

    cover_path = Path(cover_path_str)

    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
        title_page_path = Path(tmp_file.name)

    try:
        await tg_file.download_to_drive(title_page_path)
        await _run_and_reply(update, context, cover_path, title_page_path)
    finally:
        title_page_path.unlink(missing_ok=True)
        cover_path.unlink(missing_ok=True)
        context.user_data.pop(_COVER_PATH_KEY, None)  # type: ignore[union-attr]

    return ConversationHandler.END


async def handle_no_title_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2b: user indicated there is no title page — run workflow with cover only."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    cover_path_str: str | None = context.user_data.get(_COVER_PATH_KEY)  # type: ignore[union-attr]
    if not cover_path_str:
        await query.edit_message_text("Algo deu errado. Por favor, envie a capa do livro novamente.")
        return ConversationHandler.END

    cover_path = Path(cover_path_str)
    await query.edit_message_text("Ok, vou seguir sem a folha de rosto...")

    try:
        await _run_and_reply(update, context, cover_path, None)
    finally:
        cover_path.unlink(missing_ok=True)
        context.user_data.pop(_COVER_PATH_KEY, None)  # type: ignore[union-attr]

    return ConversationHandler.END


async def _run_and_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cover_path: Path,
    title_page_path: Path | None,
) -> None:
    """Run BookwormWorkflow and send formatted result to the user."""
    # resolve the message to reply to (callback queries don't have update.message)
    effective_message = update.effective_message

    loop = asyncio.get_running_loop()

    async def _send_progress(text: str) -> None:
        if effective_message is not None:
            await effective_message.reply_text(text)

    def on_progress(text: str) -> None:
        asyncio.run_coroutine_threadsafe(_send_progress(text), loop)

    try:
        result = await asyncio.to_thread(_run_workflow, cover_path, title_page_path, on_progress)
        reply = _format_result(result)
    except NotABookCoverError:
        reply = (
            "Hmm, não consegui identificar uma capa de livro nessa foto. "
            "Pode enviar uma imagem mais direta da capa frontal, bem iluminada e sem muito desfoque?"
        )
    except Exception as exc:
        user = update.effective_user
        username = user.username if user else "unknown"
        bot_log.error(f"[{username}] BookwormWorkflow failed — {exc}")
        reply = "Desculpe, não consegui identificar o livro. Por favor, tente com uma foto mais nítida."

    if effective_message is not None:
        await effective_message.reply_text(reply)


def _run_workflow(
    file_path: Path,
    title_page_path: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    wf = BookwormWorkflow()
    wf.on_progress = on_progress
    return wf.run(file_path, title_page_path=title_page_path)


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

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, handle_cover_photo)],
        states={
            _WAITING_TITLE_PAGE: [
                MessageHandler(filters.PHOTO, handle_title_page_photo),
                CallbackQueryHandler(handle_no_title_page, pattern="^no_title_page$"),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        per_user=True,
        per_chat=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))
    app.run_polling()


if __name__ == "__main__":
    main()
