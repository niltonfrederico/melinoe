"""Telegram bot: receives book cover photos and returns bibliographic analysis via BookwormWorkflow."""

import asyncio
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import ApplicationBuilder
from telegram.ext import BaseHandler
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ContextTypes
from telegram.ext import ConversationHandler
from telegram.ext import MessageHandler
from telegram.ext import filters

from melinoe.logger import bot_log
from melinoe.settings import TELEGRAM_BOT_TOKEN
from melinoe.workflows.bookworm import BookAlreadyRegisteredError
from melinoe.workflows.bookworm import BookwormWorkflow
from melinoe.workflows.bookworm import NotABookCoverError
from melinoe.workflows.kardo_navalha import KardoNavalhaWorkflow
from melinoe.workflows.kardo_navalha import ProfessorWorkAlreadyRegisteredError
from melinoe.workflows.skills.professor_detector import ProfessorDetectionResult
from melinoe.workflows.skills.professor_detector import ProfessorDetectorSkill

# Conversation states
_WAITING_TITLE_PAGE = 1
_WAITING_BOOK_CONFIRMATION = 2
_WAITING_PROFESSOR_CONFIRMATION = 3

# user_data keys
_COVER_PATH_KEY = "cover_tmp_path"
_TITLE_PAGE_PATH_KEY = "title_page_tmp_path"
_PROFESSOR_DETECTION_KEY = "professor_detection"

_BotHandlers = list[BaseHandler[Update, ContextTypes.DEFAULT_TYPE, object]]
_confidence_labels: dict[str, str] = {"high": "alta", "medium": "média", "low": "baixa"}


async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> object:
    if update.message is None:
        return
    await update.message.reply_text("Olá! Sou a Melinoe. Como posso ajudar?")


async def log_message(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    user = update.effective_user
    username = user.username if user else "unknown"
    bot_log.info("[%s] %s", username, update.message.text)


async def handle_cover_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
    """Step 1: receive cover photo, validate it, then ask for title page."""
    if update.message is None or not update.message.photo:
        return ConversationHandler.END
    if context.user_data is None:
        return ConversationHandler.END

    user = update.effective_user
    username = user.username if user else "unknown"
    bot_log.info("[%s] cover photo received", username)

    await update.message.reply_text("Foto recebida! Deixa eu verificar se é uma capa de livro...")

    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        await tg_file.download_to_drive(tmp_path)
    except Exception as exc:
        bot_log.error("Failed to download cover — %s", exc)
        tmp_path.unlink(missing_ok=True)
        await update.message.reply_text("Não consegui baixar a foto. Por favor, tente novamente.")
        return ConversationHandler.END

    # Store path for use in the next step; previous temp file (if any) is cleaned up
    old_cover: str | None = context.user_data.get(_COVER_PATH_KEY)
    if old_cover:
        Path(old_cover).unlink(missing_ok=True)
    context.user_data[_COVER_PATH_KEY] = str(tmp_path)

    # Run professor detection before asking for title page
    await update.message.reply_text("Verificando...")
    detection = await asyncio.to_thread(_run_professor_detection, tmp_path)

    if detection.is_professor_work and detection.confidence == "high":
        context.user_data[_PROFESSOR_DETECTION_KEY] = asdict(detection)
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Sim, é do Professor", callback_data="confirm_professor"),
                    InlineKeyboardButton("Não, outro livro", callback_data="deny_professor"),
                ]
            ]
        )
        await update.message.reply_text(
            "Esta parece ser uma obra de Nilton Manoel (O Professor). É isso mesmo?",
            reply_markup=keyboard,
        )
        return _WAITING_PROFESSOR_CONFIRMATION

    if detection.is_professor_work and detection.confidence == "medium":
        context.user_data[_PROFESSOR_DETECTION_KEY] = asdict(detection)
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Sim, é do Professor", callback_data="confirm_professor"),
                    InlineKeyboardButton("Não, outro livro", callback_data="deny_professor"),
                ]
            ]
        )
        await update.message.reply_text(
            "Esta obra pode ser de autoria de Nilton Manoel (O Professor). É um trabalho dele?",
            reply_markup=keyboard,
        )
        return _WAITING_PROFESSOR_CONFIRMATION

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Não tem folha de rosto", callback_data="no_title_page")]])
    await update.message.reply_text(
        "Tem a folha de rosto do livro? Envie uma foto ou indique abaixo se não tiver.",
        reply_markup=keyboard,
    )
    return _WAITING_TITLE_PAGE


async def handle_professor_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
    """User confirmed this is a Professor work — route to KardoNavalhaWorkflow."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text("Certo! Catalogando com Kardo Navalha...")

    if context.user_data is None:
        return ConversationHandler.END

    cover_path_str: str | None = context.user_data.get(_COVER_PATH_KEY)
    if not cover_path_str:
        if update.effective_message is not None:
            await update.effective_message.reply_text("Algo deu errado. Por favor, envie a imagem novamente.")
        return ConversationHandler.END

    raw_detection: dict[str, Any] | None = context.user_data.get(_PROFESSOR_DETECTION_KEY)
    detection: ProfessorDetectionResult | None = None
    if raw_detection:
        detection = ProfessorDetectionResult(**raw_detection)

    loop = asyncio.get_running_loop()
    effective_message = update.effective_message

    async def _send_progress(text: str) -> None:
        if effective_message is not None:
            await effective_message.reply_text(text)

    def on_progress(text: str) -> None:
        asyncio.run_coroutine_threadsafe(_send_progress(text), loop)

    try:
        result = await asyncio.to_thread(_run_professor_workflow, Path(cover_path_str), detection, on_progress)
        reply = _format_professor_result(result)
    except ProfessorWorkAlreadyRegisteredError:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Atualizar", callback_data="update_professor"),
                    InlineKeyboardButton("Cancelar", callback_data="restart_book"),
                ]
            ]
        )
        if effective_message is not None:
            await effective_message.reply_text(
                "Já tenho este trabalho registrado. Quer atualizar?",
                reply_markup=keyboard,
            )
        return _WAITING_BOOK_CONFIRMATION
    except Exception as exc:
        user = update.effective_user
        username = user.username if user else "unknown"
        bot_log.error("[%s] KardoNavalhaWorkflow failed — %s", username, exc)
        reply = "Não consegui catalogar este trabalho. Por favor, tente com uma foto mais nítida."
    else:
        if effective_message is not None:
            await effective_message.reply_text(reply)
        _cleanup_paths(context)
        return ConversationHandler.END

    if effective_message is not None:
        await effective_message.reply_text(reply)
    _cleanup_paths(context)
    return ConversationHandler.END


async def handle_professor_denied(update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
    """User denied Professor authorship — continue with normal title page flow."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    if context.user_data is not None:
        context.user_data.pop(_PROFESSOR_DETECTION_KEY, None)

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Não tem folha de rosto", callback_data="no_title_page")]])
    await query.edit_message_text(
        "Ok! Tem a folha de rosto do livro? Envie uma foto ou indique abaixo se não tiver.",
        reply_markup=keyboard,
    )
    return _WAITING_TITLE_PAGE


async def handle_title_page_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
    """Step 2a: user sent a title page photo — store it and run the workflow."""
    if update.message is None or not update.message.photo:
        return _WAITING_TITLE_PAGE
    if context.user_data is None:
        return ConversationHandler.END

    if not context.user_data.get(_COVER_PATH_KEY):
        await update.message.reply_text("Algo deu errado. Por favor, envie a capa do livro novamente.")
        return ConversationHandler.END

    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
        title_page_path = Path(tmp_file.name)

    try:
        await tg_file.download_to_drive(title_page_path)
    except Exception as exc:
        bot_log.error("Failed to download title page — %s", exc)
        title_page_path.unlink(missing_ok=True)
        await update.message.reply_text("Não consegui baixar a foto. Por favor, tente novamente.")
        return _WAITING_TITLE_PAGE

    context.user_data[_TITLE_PAGE_PATH_KEY] = str(title_page_path)
    return await _run_and_maybe_confirm(update, context)


async def handle_no_title_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
    """Step 2b: user indicated there is no title page — run workflow with cover only."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()

    if context.user_data is None:
        await query.edit_message_text("Algo deu errado. Por favor, envie a capa do livro novamente.")
        return ConversationHandler.END

    if not context.user_data.get(_COVER_PATH_KEY):
        await query.edit_message_text("Algo deu errado. Por favor, envie a capa do livro novamente.")
        return ConversationHandler.END

    await query.edit_message_text("Ok, vou seguir sem a folha de rosto...")
    context.user_data.pop(_TITLE_PAGE_PATH_KEY, None)
    return await _run_and_maybe_confirm(update, context)


async def handle_book_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
    """Confirmation: user wants to update the existing registration."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text("Certo! Atualizando o registro...")

    if context.user_data is None:
        return ConversationHandler.END

    cover_path_str: str | None = context.user_data.get(_COVER_PATH_KEY)
    title_page_path_str: str | None = context.user_data.get(_TITLE_PAGE_PATH_KEY)
    if not cover_path_str:
        if update.effective_message is not None:
            await update.effective_message.reply_text("Algo deu errado. Por favor, envie a capa do livro novamente.")
        return ConversationHandler.END

    try:
        await _run_and_reply(
            update,
            context,
            Path(cover_path_str),
            Path(title_page_path_str) if title_page_path_str else None,
            force_update=True,
        )
    finally:
        _cleanup_paths(context)

    return ConversationHandler.END


async def handle_book_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
    """Confirmation: user wants to start fresh — discard current session."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text("Ok! Manda uma nova foto da capa quando quiser.")
    _cleanup_paths(context)
    return ConversationHandler.END


def _cleanup_paths(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data is None:
        return
    for key in (_COVER_PATH_KEY, _TITLE_PAGE_PATH_KEY):
        path_str: str | None = context.user_data.pop(key, None)
        if path_str:
            Path(path_str).unlink(missing_ok=True)


async def _run_and_maybe_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> object:
    """Run the workflow; if the book is already registered, ask the user what to do."""
    if context.user_data is None:
        return ConversationHandler.END

    cover_path_str: str | None = context.user_data.get(_COVER_PATH_KEY)
    title_page_path_str: str | None = context.user_data.get(_TITLE_PAGE_PATH_KEY)
    if not cover_path_str:
        return ConversationHandler.END

    try:
        await _run_and_reply(
            update,
            context,
            Path(cover_path_str),
            Path(title_page_path_str) if title_page_path_str else None,
        )
        _cleanup_paths(context)
        return ConversationHandler.END
    except _BookAlreadyRegisteredError as exc:
        title_display = f'"{exc.title}"' + (f" de {exc.author}" if exc.author else "")
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Atualizar", callback_data="update_book"),
                    InlineKeyboardButton("Começar do zero", callback_data="restart_book"),
                ]
            ]
        )
        effective_message = update.effective_message
        if effective_message is not None:
            await effective_message.reply_text(
                f"Já tenho {title_display} registrado. Quer atualizar o registro ou começar do zero?",
                reply_markup=keyboard,
            )
        return _WAITING_BOOK_CONFIRMATION


class _BookAlreadyRegisteredError(Exception):
    def __init__(self, err: BookAlreadyRegisteredError) -> None:
        self.title = err.title
        self.author = err.author
        super().__init__()


async def _run_and_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cover_path: Path,
    title_page_path: Path | None,
    force_update: bool = False,
) -> None:
    """Run BookwormWorkflow and send formatted result to the user."""
    effective_message = update.effective_message
    loop = asyncio.get_running_loop()

    async def _send_progress(text: str) -> None:
        if effective_message is not None:
            await effective_message.reply_text(text)

    def on_progress(text: str) -> None:
        asyncio.run_coroutine_threadsafe(_send_progress(text), loop)

    try:
        result = await asyncio.to_thread(_run_workflow, cover_path, title_page_path, on_progress, force_update)
        reply = _format_result(result)
    except BookAlreadyRegisteredError as exc:
        raise _BookAlreadyRegisteredError(exc) from exc
    except NotABookCoverError:
        reply = (
            "Hmm, não consegui identificar uma capa de livro nessa foto. "
            "Pode enviar uma imagem mais direta da capa frontal, bem iluminada e sem muito desfoque?"
        )
    except Exception as exc:
        user = update.effective_user
        username = user.username if user else "unknown"
        bot_log.error("[%s] BookwormWorkflow failed — %s", username, exc)
        reply = "Desculpe, não consegui identificar o livro. Por favor, tente com uma foto mais nítida."
    else:
        if effective_message is not None:
            await effective_message.reply_text(reply)
        return

    if effective_message is not None:
        await effective_message.reply_text(reply)


def _run_workflow(
    file_path: Path,
    title_page_path: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
    force_update: bool = False,
) -> dict[str, Any]:
    wf = BookwormWorkflow()
    wf.on_progress = on_progress
    return wf.run(file_path, title_page_path=title_page_path, force_update=force_update)


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


def _run_professor_detection(file_path: Path) -> ProfessorDetectionResult:
    detector = ProfessorDetectorSkill()
    return detector.run(file_path)


def _run_professor_workflow(
    cover_path: Path,
    detection: ProfessorDetectionResult | None,
    on_progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    wf = KardoNavalhaWorkflow()
    wf.on_progress = on_progress
    return wf.run(cover_path, detection=detection)


def _format_professor_result(result: dict[str, Any]) -> str:
    catalog: dict[str, Any] = result.get("catalog") or {}
    confidence: str = result.get("report_confidence", "low")

    title = catalog.get("title") or "Título não identificado"
    work_type = catalog.get("work_type") or "obra"
    literary_form = catalog.get("literary_form")
    pseudonym = catalog.get("pseudonym")
    year = catalog.get("year_estimate")
    year_is_estimate = catalog.get("year_is_estimate", True)
    publication_context = catalog.get("publication_context")
    location = catalog.get("location")
    competition_info = catalog.get("competition_info")
    tags = catalog.get("tags") or []
    notes = catalog.get("notes")

    lines: list[str] = [f"*{title}*"]
    lines.append("por Nilton Manoel (O Professor)")

    if pseudonym:
        lines.append(f"Pseudônimo: {pseudonym}")

    type_line = work_type
    if literary_form:
        type_line += f" — {literary_form}"
    lines.append(f"Tipo: {type_line}")

    if year:
        year_str = f"~{year}" if year_is_estimate else str(year)
        lines.append(f"Ano: {year_str}")

    if location:
        lines.append(f"Local: {location}")

    if publication_context:
        lines.append(f"Contexto: {publication_context}")

    if competition_info:
        lines.append(f"Competição: {competition_info}")

    if tags:
        lines.append(f"Tags: {', '.join(tags)}")

    if notes:
        short = notes[:300] + ("..." if len(notes) > 300 else "")
        lines.append(f"\n{short}")

    confidence_label = _confidence_labels.get(confidence, confidence)
    lines.append(f"\nConfiança: {confidence_label}")
    return "\n".join(lines)


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    entry_points: _BotHandlers = [MessageHandler(filters.PHOTO, handle_cover_photo)]
    professor_confirmation_handlers: _BotHandlers = [
        CallbackQueryHandler(handle_professor_confirmed, pattern="^confirm_professor$"),
        CallbackQueryHandler(handle_professor_denied, pattern="^deny_professor$"),
    ]
    title_page_handlers: _BotHandlers = [
        MessageHandler(filters.PHOTO, handle_title_page_photo),
        CallbackQueryHandler(handle_no_title_page, pattern="^no_title_page$"),
    ]
    confirmation_handlers: _BotHandlers = [
        CallbackQueryHandler(handle_book_update, pattern="^update_book$"),
        CallbackQueryHandler(handle_book_restart, pattern="^restart_book$"),
    ]
    fallback_handlers: _BotHandlers = [CommandHandler("start", start)]
    states: dict[object, _BotHandlers] = {
        _WAITING_PROFESSOR_CONFIRMATION: professor_confirmation_handlers,
        _WAITING_TITLE_PAGE: title_page_handlers,
        _WAITING_BOOK_CONFIRMATION: confirmation_handlers,
    }

    conv_handler = ConversationHandler(
        entry_points=entry_points,
        states=states,
        fallbacks=fallback_handlers,
        per_user=True,
        per_chat=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_message))
    app.run_polling()


if __name__ == "__main__":
    main()
