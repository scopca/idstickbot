"""Telegram bot that reports sticker file IDs and premium custom emoji IDs."""

import asyncio
import logging
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import MessageEntityType, ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, MessageEntity

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
)

dp = Dispatcher()


def get_entity_text(message: Message, entity: MessageEntity) -> str | None:
    """Return the substring covered by the entity (Telegram offsets are UTF-16 based)."""
    text = message.text or message.caption
    if not text or entity.offset is None or entity.length is None:
        return None
    raw = text.encode("utf-16-le")
    chunk = raw[entity.offset * 2 : (entity.offset + entity.length) * 2]
    return chunk.decode("utf-16-le", errors="replace") or None


def extract_custom_emojis(message: Message) -> list[tuple[str, str]]:
    """Return unique (default_emoji, custom_emoji_id) pairs from text and captions."""
    entities = [*(message.entities or []), *(message.caption_entities or [])]
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entity in entities:
        if entity.type != MessageEntityType.CUSTOM_EMOJI or not entity.custom_emoji_id:
            continue
        if entity.custom_emoji_id in seen:
            continue
        seen.add(entity.custom_emoji_id)
        default_emoji = get_entity_text(message, entity) or "\u2753"
        result.append((default_emoji, entity.custom_emoji_id))
    return result


def format_ids(ids: list[str]) -> str:
    """Put every ID into its own <code> block so one tap copies exactly that ID."""
    return "\n".join(f"<code>{item}</code>" for item in ids)


def format_custom_emojis(emojis: list[tuple[str, str]]) -> str:
    """Show each default emoji followed by its custom_emoji_id."""
    return "\n".join(f"{emoji} <code>{custom_emoji_id}</code>" for emoji, custom_emoji_id in emojis)


@dp.message(CommandStart())
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
    if sticker.is_video:
        kind = "Video sticker"
    elif sticker.is_animated:
        kind = "Animated sticker"
    else:
        kind = "Sticker"
    await message.reply(f"{kind} file_id:\n{format_ids([sticker.file_id])}")


@dp.message(F.entities | F.caption_entities)
async def handle_custom_emoji(message: Message) -> None:
    emojis = extract_custom_emojis(message)
    if not emojis:
        await message.reply("No premium custom emoji found in this message.")
        return
    plural = "IDs" if len(emojis) > 1 else "ID"
    await message.reply(f"Custom emoji {plural}:\n{format_custom_emojis(emojis)}")


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "No token provided. Copy .env.example to .env and set BOT_TOKEN."
        )
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
