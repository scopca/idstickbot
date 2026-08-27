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
from aiogram.types import BotCommand, Message, MessageEntity

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
    await message.answer(
        "Send me:\n"
        "\u2022 a sticker \u2014 I'll reply with its file_id\n"
        "\u2022 any message with premium custom emoji \u2014 I'll reply "
        "with each emoji's default and its custom_emoji_id\n\n"
        "Every ID sits in its own monospace block \u2014 tap it to copy.",
    )


@dp.message(F.sticker)
async def handle_sticker(message: Message) -> None:
    sticker = message.sticker
    if not sticker:
        return
    if sticker.is_video:
        kind = "Video sticker"
    elif sticker.is_animated:
        kind = "Animated sticker"
    elif sticker.type == "custom_emoji":
        kind = "Custom emoji sticker"
    else:
        kind = "Sticker"

    parts: list[str] = [
        f"{kind} file_id:\n{format_ids([sticker.file_id])}",
        f"file_unique_id:\n{format_ids([sticker.file_unique_id])}",
    ]
    if sticker.set_name:
        parts.append(f"Set: <code>{html.escape(sticker.set_name)}</code>")
    if sticker.emoji:
        parts.append(f"Emoji: {html.escape(sticker.emoji)}")
    # custom_emoji_id is present for custom_emoji type
    if getattr(sticker, "custom_emoji_id", None):
        parts.append(f"custom_emoji_id:\n{format_ids([sticker.custom_emoji_id])}")

    await message.reply("\n\n".join(parts))


@dp.message(F.entities | F.caption_entities)
async def handle_custom_emoji(message: Message) -> None:
    emojis = extract_custom_emojis(message)
    if not emojis:
        return
    plural = "IDs" if len(emojis) > 1 else "ID"
    await message.reply(f"Custom emoji {plural}:\n{format_custom_emojis(emojis)}")


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
                    BotCommand(command="start", description="Show help"),
                    BotCommand(command="help", description="Show help"),
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
