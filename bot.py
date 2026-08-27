"""Telegram bot that reports sticker file IDs and premium custom emoji IDs."""

import asyncio
import html
import logging
import logging.handlers
import os
import pathlib

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import MessageEntityType, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    MessageEntity,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

load_dotenv()
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()

# Robust logging: rotating file + console (no longer relies on shell redirection)
LOG_FILE = pathlib.Path(__file__).with_name("bot.log")
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    handlers=[_file_handler, logging.StreamHandler()],
)

dp = Dispatcher()

# ── Keyboards & Texts ──────────────────────────────────────────────

BTN_STICKER = "🎨 Sticker Guide"
BTN_EMOJI = "✨ Emoji Guide"
BTN_ABOUT = "ℹ️ About"
BTN_HIDE = "❌ Hide Keyboard"

HELP_TEXT = (
    "<b>👋 Welcome to ID Stick Bot!</b>\n\n"
    "<b>🎨 Stickers</b>\n"
    "Send me any sticker — I’ll reply with:\n"
    "• <code>file_id</code> — use in <code>sendSticker</code>\n"
    "• <code>file_unique_id</code> — for logging / dedup\n"
    "• <code>set_name</code> &amp; emoji if available\n\n"
    "<b>✨ Premium Custom Emoji</b>\n"
    "Send a message <i>with</i> a Premium emoji or a photo with emoji in the caption\n"
    "— I’ll reply with each <code>custom_emoji_id</code>.\n\n"
    "<b>💡 Tip</b>\n"
    "Every ID is in its own <code>code</code> block — tap to copy.\n\n"
    "Use the keyboard below or /help anytime."
)

STICKER_GUIDE_TEXT = (
    "<b>🎨 How to get a sticker ID</b>\n\n"
    "1. Open any chat → tap the <b>sticker</b> panel\n"
    "2. Send any sticker to me (forwarded also works)\n"
    "3. I’ll reply with:\n"
    "   • <b>file_id</b> — for your bot\n"
    "   • <b>file_unique_id</b> — short, stable across bots\n"
    "   • <b>set_name</b> — call <code>getStickerSet</code> with it\n\n"
    "I detect: <i>Static</i> · <i>Animated (.tgs)</i> · <i>Video (.webm)</i> · <i>Custom Emoji</i>"
)

EMOJI_GUIDE_TEXT = (
    "<b>✨ How to get a custom emoji ID</b>\n\n"
    "1. Type a message containing a <b>Premium custom emoji</b> (not a normal 😀)\n"
    "2. Or send a photo with a Premium emoji in the <b>caption</b>\n"
    "3. I’ll reply:\n"
    "   <code>😀 &lt;custom_emoji_id&gt;</code>\n\n"
    "<b>Note:</b> Regular Unicode emojis have no ID — I’ll stay silent.\n"
    "Duplicates in one message are de-duplicated."
)

ABOUT_TEXT = (
    "<b>ℹ️ About ID Stick Bot</b>\n\n"
    "Fast, minimal, open-source — built for developers, sticker makers &amp; bot builders.\n\n"
    "<b>Stack:</b> Python 3.12 · aiogram 3.30 · HTML parse mode\n"
    "<b>Privacy:</b> I only read sticker / emoji IDs — no storage, no tracking.\n\n"
    "Enjoying it? ⭐ Star it on GitHub or share the bot!"
)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_STICKER), KeyboardButton(text=BTN_EMOJI)],
            [KeyboardButton(text=BTN_ABOUT), KeyboardButton(text=BTN_HIDE)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Send a sticker or Premium emoji…",
    )


def get_about_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📂 GitHub", url="https://github.com/algorithco/idstickbot"),
                InlineKeyboardButton(text="🤖 Share bot", url="https://t.me/share/url?url=https://t.me/idstickrobot"),
            ],
            [InlineKeyboardButton(text="💬 BotFather", url="https://t.me/BotFather")],
        ]
    )


def _get_text_for_entity(text: str | None, entity: MessageEntity) -> str | None:
    """Return substring for entity where text is already the correct field (text or caption)."""
    if not text or entity.offset is None or entity.length is None:
        return None
    raw = text.encode("utf-16-le")
    units = len(raw) // 2
    if entity.offset < 0 or entity.length <= 0 or entity.offset + entity.length > units:
        return None
    chunk = raw[entity.offset * 2 : (entity.offset + entity.length) * 2]
    return chunk.decode("utf-16-le", errors="replace") or None


def get_entity_text(message: Message, entity: MessageEntity) -> str | None:
    """Return the substring covered by the entity (Telegram offsets are UTF-16 based)."""
    # Prefer the field that actually owns the entity to avoid offset mismatch.
    # Telegram never sends both text and caption, but handle both safely.
    if message.entities and entity in message.entities:
        return _get_text_for_entity(message.text, entity)
    if message.caption_entities and entity in message.caption_entities:
        return _get_text_for_entity(message.caption, entity)
    # Fallback: try text then caption
    return _get_text_for_entity(message.text or message.caption, entity)


def extract_custom_emojis(message: Message) -> list[tuple[str, str]]:
    """Return unique (default_emoji, custom_emoji_id) pairs from text and captions."""
    result: list[tuple[str, str]] = []
    seen: set[str] = set()

    # Iterate per-field so offsets are resolved against the correct string
    for entity in message.entities or []:
        if entity.type != MessageEntityType.CUSTOM_EMOJI or not entity.custom_emoji_id:
            continue
        if entity.custom_emoji_id in seen:
            continue
        seen.add(entity.custom_emoji_id)
        default_emoji = _get_text_for_entity(message.text, entity) or "\u2753"
        result.append((default_emoji, entity.custom_emoji_id))

    for entity in message.caption_entities or []:
        if entity.type != MessageEntityType.CUSTOM_EMOJI or not entity.custom_emoji_id:
            continue
        if entity.custom_emoji_id in seen:
            continue
        seen.add(entity.custom_emoji_id)
        default_emoji = _get_text_for_entity(message.caption, entity) or "\u2753"
        result.append((default_emoji, entity.custom_emoji_id))

    return result


def format_ids(ids: list[str]) -> str:
    """Put every ID into its own <code> block so one tap copies exactly that ID."""
    return "\n".join(f"<code>{html.escape(item)}</code>" for item in ids)


def format_custom_emojis(emojis: list[tuple[str, str]]) -> str:
    """Show each default emoji followed by its custom_emoji_id."""
    return "\n".join(
        f"{html.escape(emoji)} <code>{html.escape(custom_emoji_id)}</code>"
        for emoji, custom_emoji_id in emojis
    )


@dp.message(CommandStart())
@dp.message(Command("help"))
async def cmd_start(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=get_main_keyboard())


@dp.message(F.text == BTN_STICKER)
async def btn_sticker_guide(message: Message) -> None:
    await message.answer(STICKER_GUIDE_TEXT)


@dp.message(F.text == BTN_EMOJI)
async def btn_emoji_guide(message: Message) -> None:
    await message.answer(EMOJI_GUIDE_TEXT)


@dp.message(F.text == BTN_ABOUT)
async def btn_about(message: Message) -> None:
    await message.answer(ABOUT_TEXT, reply_markup=get_about_keyboard())


@dp.message(F.text == BTN_HIDE)
async def btn_hide(message: Message) -> None:
    await message.answer(
        "Keyboard hidden — send /start to show it again.",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(F.sticker)
async def handle_sticker(message: Message) -> None:
    sticker = message.sticker
    if not sticker:
        return
    if sticker.is_video:
        kind = "Video sticker"
        icon = "🎬"
    elif sticker.is_animated:
        kind = "Animated sticker"
        icon = "✨"
    elif sticker.type == "custom_emoji":
        kind = "Custom emoji sticker"
        icon = "😀"
    else:
        kind = "Sticker"
        icon = "🎨"

    parts: list[str] = [
        f"<b>{icon} {kind}</b>",
        f"<b>file_id:</b>\n{format_ids([sticker.file_id])}",
        f"<b>file_unique_id:</b>\n{format_ids([sticker.file_unique_id])}",
    ]
    if sticker.set_name:
        parts.append(f"<b>Set:</b> <code>{html.escape(sticker.set_name)}</code>")
    if sticker.emoji:
        parts.append(f"<b>Emoji:</b> {html.escape(sticker.emoji)}")
    # custom_emoji_id is present for custom_emoji type
    if getattr(sticker, "custom_emoji_id", None):
        parts.append(f"<b>custom_emoji_id:</b>\n{format_ids([sticker.custom_emoji_id])}")

    parts.append("<i>Tap any code block to copy</i> \U0001f4cb")
    await message.reply("\n\n".join(parts))


@dp.message(F.entities | F.caption_entities)
async def handle_custom_emoji(message: Message) -> None:
    emojis = extract_custom_emojis(message)
    if not emojis:
        return
    plural = "IDs" if len(emojis) > 1 else "ID"
    header = f"<b>✨ Custom emoji {plural} — tap to copy:</b>"
    await message.reply(f"{header}\n{format_custom_emojis(emojis)}")


# Fallback for plain text (not a button, not a custom emoji) — gentle hint, not spammy in groups
@dp.message(F.text)
async def handle_text_fallback(message: Message) -> None:
    # Already handled button texts above; this is for any other text
    # Keep it helpful but not noisy: only reply in private chats
    if message.chat.type == "private":
        await message.answer(
            "👋 Send me a sticker or a message with a <b>Premium custom emoji</b> and I’ll send its ID.\n"
            "Use the buttons below for guides \U0001f447",
            reply_markup=get_main_keyboard(),
        )


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "No token provided. Copy .env.example to .env and set BOT_TOKEN."
        )
    # Use context manager so aiohttp session is closed on exit (Windows safe)
    async with Bot(
        token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    ) as bot:
        # Set commands for BotFather menu
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="✨ Show help & keyboard"),
                    BotCommand(command="help", description="🆘 Help & guides"),
                ]
            )
        except Exception:
            logging.warning("Failed to set bot commands", exc_info=True)

        drop_pending = os.getenv("DROP_PENDING_UPDATES", "false").lower() == "true"
        await bot.delete_webhook(drop_pending_updates=drop_pending)
        # handle_signals=False on Windows (add_signal_handler not supported)
        await dp.start_polling(bot, handle_signals=False)


if __name__ == "__main__":
    asyncio.run(main())
