"""Telegram bot that reports sticker file IDs and premium custom emoji IDs."""

import asyncio
import html
import json
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
    CallbackQuery,
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
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip()

# Supabase client — optional, falls back to local file if not configured
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client  # type: ignore

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logging.getLogger(__name__).info("Supabase client initialized")
    except Exception as e:
        logging.warning("Supabase init failed, falling back to local file: %s", e)
        supabase = None

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

# ── i18n ───────────────────────────────────────────────────────────

LANGS = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "uz": "🇺🇿 Oʻzbekcha",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "btn_sticker": "🎨 Sticker Guide",
        "btn_emoji": "✨ Emoji Guide",
        "btn_about": "ℹ️ About",
        "btn_hide": "❌ Hide Keyboard",
        "btn_lang": "🌐 Language",
        "placeholder": "Write a message...",
        "help": (
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
        ),
        "sticker_guide": (
            "<b>🎨 How to get a sticker ID</b>\n\n"
            "1. Open any chat → tap the <b>sticker</b> panel\n"
            "2. Send any sticker to me (forwarded also works)\n"
            "3. I’ll reply with:\n"
            "   • <b>file_id</b> — for your bot\n"
            "   • <b>file_unique_id</b> — short, stable across bots\n"
            "   • <b>set_name</b> — call <code>getStickerSet</code> with it\n\n"
            "I detect: <i>Static</i> · <i>Animated (.tgs)</i> · <i>Video (.webm)</i> · <i>Custom Emoji</i>"
        ),
        "emoji_guide": (
            "<b>✨ How to get a custom emoji ID</b>\n\n"
            "1. Type a message containing a <b>Premium custom emoji</b> (not a normal 😀)\n"
            "2. Or send a photo with a Premium emoji in the <b>caption</b>\n"
            "3. I’ll reply:\n"
            "   <code>😀 &lt;custom_emoji_id&gt;</code>\n\n"
            "<b>Note:</b> Regular Unicode emojis have no ID — I’ll stay silent.\n"
            "Duplicates in one message are de-duplicated."
        ),
        "about": (
            "<b>ℹ️ About ID Stick Bot</b>\n\n"
            "Fast, minimal, open-source — built for developers, sticker makers &amp; bot builders.\n\n"
            "<b>Stack:</b> Python 3.12 · aiogram 3.30 · HTML parse mode\n"
            "<b>Privacy:</b> I only read sticker / emoji IDs — no storage, no tracking.\n\n"
            "Enjoying it? ⭐ Star it on GitHub or share the bot!"
        ),
        "fallback": (
            "👋 Send me a sticker or a message with a <b>Premium custom emoji</b> and I’ll send its ID.\n"
            "Use the buttons below for guides \U0001f447"
        ),
        "lang_select": "🌐 Choose language:",
        "lang_changed": "✅ Language changed to English",
        "hide_confirm": "Keyboard hidden — send /start to show it again.",
        "kind_sticker": "Sticker",
        "kind_video": "Video sticker",
        "kind_animated": "Animated sticker",
        "kind_custom": "Custom emoji sticker",
        "label_file_id": "file_id:",
        "label_unique": "file_unique_id:",
        "label_set": "Set:",
        "label_emoji": "Emoji:",
        "label_custom": "custom_emoji_id:",
        "footer_copy": "Tap any code block to copy \U0001f4cb",
        "custom_header_one": "Custom emoji ID — tap to copy:",
        "custom_header_many": "Custom emoji IDs — tap to copy:",
        "cmd_start": "✨ Show help & keyboard",
        "cmd_help": "🆘 Help & guides",
        "cmd_lang": "🌐 Change language",
    },
    "ru": {
        "btn_sticker": "🎨 Гайд по стикерам",
        "btn_emoji": "✨ Гайд по эмодзи",
        "btn_about": "ℹ️ О боте",
        "btn_hide": "❌ Скрыть клавиатуру",
        "btn_lang": "🌐 Язык",
        "placeholder": "Напишите сообщение...",
        "help": (
            "<b>👋 Добро пожаловать в ID Stick Bot!</b>\n\n"
            "<b>🎨 Стикеры</b>\n"
            "Отправьте любой стикер — я отвечу:\n"
            "• <code>file_id</code> — для <code>sendSticker</code>\n"
            "• <code>file_unique_id</code> — для логов\n"
            "• <code>set_name</code> и эмодзи, если есть\n\n"
            "<b>✨ Премиум кастомные эмодзи</b>\n"
            "Отправьте сообщение с Premium эмодзи или фото с эмодзи в подписи\n"
            "— я пришлю каждый <code>custom_emoji_id</code>.\n\n"
            "<b>💡 Совет</b>\n"
            "Каждый ID в отдельном блоке <code>code</code> — нажмите чтобы скопировать.\n\n"
            "Используйте клавиатуру ниже или /help."
        ),
        "sticker_guide": (
            "<b>🎨 Как получить ID стикера</b>\n\n"
            "1. Откройте любой чат → нажмите панель <b>стикеров</b>\n"
            "2. Отправьте любой стикер мне (пересланные тоже работают)\n"
            "3. Я отвечу:\n"
            "   • <b>file_id</b> — для вашего бота\n"
            "   • <b>file_unique_id</b> — короткий, стабильный\n"
            "   • <b>set_name</b> — вызовите <code>getStickerSet</code>\n\n"
            "Определяю: <i>Статичные</i> · <i>Анимированные (.tgs)</i> · <i>Видео (.webm)</i> · <i>Кастомные эмодзи</i>"
        ),
        "emoji_guide": (
            "<b>✨ Как получить ID кастомного эмодзи</b>\n\n"
            "1. Напишите сообщение с <b>Premium кастомным эмодзи</b> (не обычный 😀)\n"
            "2. Или отправьте фото с Premium эмодзи в <b>подписи</b>\n"
            "3. Я отвечу:\n"
            "   <code>😀 &lt;custom_emoji_id&gt;</code>\n\n"
            "<b>Примечание:</b> Обычные Unicode эмодзи без ID — я промолчу.\n"
            "Дубликаты в одном сообщении удаляются."
        ),
        "about": (
            "<b>ℹ️ О боте ID Stick</b>\n\n"
            "Быстрый, минималистичный, open-source — для разработчиков, создателей стикеров и ботов.\n\n"
            "<b>Стек:</b> Python 3.12 · aiogram 3.30 · HTML\n"
            "<b>Приватность:</b> читаю только ID стикеров/эмодзи — без хранения.\n\n"
            "Нравится? ⭐ Поставьте звезду на GitHub!"
        ),
        "fallback": (
            "👋 Отправьте мне стикер или сообщение с <b>Premium кастомным эмодзи</b> и я пришлю ID.\n"
            "Кнопки ниже — подсказки \U0001f447"
        ),
        "lang_select": "🌐 Выберите язык:",
        "lang_changed": "✅ Язык изменён на Русский",
        "hide_confirm": "Клавиатура скрыта — отправьте /start чтобы показать снова.",
        "kind_sticker": "Стикер",
        "kind_video": "Видео-стикер",
        "kind_animated": "Анимированный стикер",
        "kind_custom": "Кастомный эмодзи-стикер",
        "label_file_id": "file_id:",
        "label_unique": "file_unique_id:",
        "label_set": "Набор:",
        "label_emoji": "Эмодзи:",
        "label_custom": "custom_emoji_id:",
        "footer_copy": "Нажмите на любой блок кода чтобы скопировать \U0001f4cb",
        "custom_header_one": "ID кастомного эмодзи — нажмите чтобы скопировать:",
        "custom_header_many": "ID кастомных эмодзи — нажмите чтобы скопировать:",
        "cmd_start": "✨ Помощь и клавиатура",
        "cmd_help": "🆘 Помощь",
        "cmd_lang": "🌐 Сменить язык",
    },
    "uz": {
        "btn_sticker": "🎨 Stiker qo‘llanma",
        "btn_emoji": "✨ Emoji qo‘llanma",
        "btn_about": "ℹ️ Bot haqida",
        "btn_hide": "❌ Klaviaturani yashirish",
        "btn_lang": "🌐 Til",
        "placeholder": "Xabar yozing...",
        "help": (
            "<b>👋 ID Stick Botiga xush kelibsiz!</b>\n\n"
            "<b>🎨 Stikerlar</b>\n"
            "Har qanday stiker yuboring — men javob beraman:\n"
            "• <code>file_id</code> — <code>sendSticker</code> uchun\n"
            "• <code>file_unique_id</code> — loglar uchun\n"
            "• <code>set_name</code> va emoji, agar mavjud bo‘lsa\n\n"
            "<b>✨ Premium maxsus emoji</b>\n"
            "Premium emoji bilan xabar yoki emoji bilan foto sarlavhasi yuboring\n"
            "— har bir <code>custom_emoji_id</code> ni yuboraman.\n\n"
            "<b>💡 Maslahat</b>\n"
            "Har bir ID alohida <code>code</code> blokida — nusxalash uchun bosing.\n\n"
            "Pastdagi klaviaturadan yoki /help dan foydalaning."
        ),
        "sticker_guide": (
            "<b>🎨 Stiker ID sini qanday olish</b>\n\n"
            "1. Istalgan chatni oching → <b>stiker</b> panelini bosing\n"
            "2. Menga istalgan stiker yuboring (yo‘naltirilgan ham bo‘ladi)\n"
            "3. Men javob beraman:\n"
            "   • <b>file_id</b> — botingiz uchun\n"
            "   • <b>file_unique_id</b> — qisqa, barqaror\n"
            "   • <b>set_name</b> — <code>getStickerSet</code> ni chaqiring\n\n"
            "Aniqlayman: <i>Statik</i> · <i>Animatsion (.tgs)</i> · <i>Video (.webm)</i> · <i>Maxsus emoji</i>"
        ),
        "emoji_guide": (
            "<b>✨ Maxsus emoji ID sini qanday olish</b>\n\n"
            "1. <b>Premium maxsus emoji</b> bilan xabar yozing (oddiy 😀 emas)\n"
            "2. Yoki sarlavhada Premium emoji bilan foto yuboring\n"
            "3. Men javob beraman:\n"
            "   <code>😀 &lt;custom_emoji_id&gt;</code>\n\n"
            "<b>Eslatma:</b> Oddiy Unicode emojilarda ID yo‘q — men jim turaman.\n"
            "Bir xabardagi takrorlar olib tashlanadi."
        ),
        "about": (
            "<b>ℹ️ ID Stick Bot haqida</b>\n\n"
            "Tez, minimal, open-source — dasturchilar, stiker yaratuvchilar va bot quruvchilar uchun.\n\n"
            "<b>Stek:</b> Python 3.12 · aiogram 3.30 · HTML\n"
            "<b>Maxfiylik:</b> faqat stiker/emoji ID larini o‘qiyman — saqlamayman.\n\n"
            "Yoqtimi? ⭐ GitHub da yulduzcha bosing!"
        ),
        "fallback": (
            "👋 Menga stiker yoki <b>Premium maxsus emoji</b> bilan xabar yuboring va ID ni yuboraman.\n"
            "Pastdagi tugmalar — qo‘llanmalar \U0001f447"
        ),
        "lang_select": "🌐 Tilni tanlang:",
        "lang_changed": "✅ Til Oʻzbekchaga oʻzgartirildi",
        "hide_confirm": "Klaviatura yashirildi — qaytarish uchun /start yuboring.",
        "kind_sticker": "Stiker",
        "kind_video": "Video stiker",
        "kind_animated": "Animatsion stiker",
        "kind_custom": "Maxsus emoji stiker",
        "label_file_id": "file_id:",
        "label_unique": "file_unique_id:",
        "label_set": "To‘plam:",
        "label_emoji": "Emoji:",
        "label_custom": "custom_emoji_id:",
        "footer_copy": "Nusxalash uchun istalgan kod blokini bosing \U0001f4cb",
        "custom_header_one": "Maxsus emoji ID — nusxalash uchun bosing:",
        "custom_header_many": "Maxsus emoji ID lari — nusxalash uchun bosing:",
        "cmd_start": "✨ Yordam va klaviatura",
        "cmd_help": "🆘 Yordam",
        "cmd_lang": "🌐 Tilni o‘zgartirish",
    },
}

LANG_FILE = pathlib.Path(__file__).with_name("user_langs.json")
_user_langs: dict[str, str] = {}


def _load_langs() -> None:
    global _user_langs
    if LANG_FILE.exists():
        try:
            _user_langs = json.loads(LANG_FILE.read_text(encoding="utf-8"))
        except Exception:
            _user_langs = {}
    else:
        _user_langs = {}


def _save_langs() -> None:
    try:
        LANG_FILE.write_text(json.dumps(_user_langs, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logging.warning("Failed to save langs", exc_info=True)


_load_langs()


def get_user_lang(user_id: int | None, fallback_code: str | None = None) -> str:
    # 1. Try Supabase if configured (persistent, works on Render ephemeral FS)
    if user_id is not None and supabase is not None:
        try:
            res = supabase.table("user_langs").select("lang").eq("user_id", user_id).execute()
            if res.data and len(res.data) > 0:
                lang = res.data[0].get("lang")
                if lang in LANGS:
                    return lang
        except Exception as e:
            logging.debug("Supabase get_user_lang failed, falling back to file: %s", e)
    # 2. Fallback to local file cache
    if user_id is not None and str(user_id) in _user_langs:
        lang = _user_langs[str(user_id)]
        if lang in LANGS:
            return lang
    if fallback_code:
        code = fallback_code.split("-")[0].lower()
        if code in LANGS:
            return code
    return "en"


def set_user_lang(user_id: int, lang: str) -> None:
    if lang not in LANGS:
        return
    # 1. Try Supabase first
    if supabase is not None:
        try:
            supabase.table("user_langs").upsert(
                {"user_id": user_id, "lang": lang}, on_conflict="user_id"
            ).execute()
            # Also keep local cache in sync
            _user_langs[str(user_id)] = lang
            return
        except Exception as e:
            logging.warning("Supabase set_user_lang failed, falling back to file: %s", e)
    # 2. Fallback to local file
    _user_langs[str(user_id)] = lang
    _save_langs()


def t(key: str, lang: str) -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))


# Build sets for button filters (all languages)
BTN_STICKER_ALL = {TRANSLATIONS[l]["btn_sticker"] for l in LANGS}
BTN_EMOJI_ALL = {TRANSLATIONS[l]["btn_emoji"] for l in LANGS}
BTN_ABOUT_ALL = {TRANSLATIONS[l]["btn_about"] for l in LANGS}
BTN_HIDE_ALL = {TRANSLATIONS[l]["btn_hide"] for l in LANGS}
BTN_LANG_ALL = {TRANSLATIONS[l]["btn_lang"] for l in LANGS}


def get_main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    tr = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=tr["btn_sticker"]), KeyboardButton(text=tr["btn_emoji"])],
            [KeyboardButton(text=tr["btn_about"]), KeyboardButton(text=tr["btn_lang"])],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=tr["placeholder"],
    )


def get_lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=LANGS["en"], callback_data="lang:en"),
                InlineKeyboardButton(text=LANGS["ru"], callback_data="lang:ru"),
            ],
            [InlineKeyboardButton(text=LANGS["uz"], callback_data="lang:uz")],
        ]
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
    if message.entities and entity in message.entities:
        return _get_text_for_entity(message.text, entity)
    if message.caption_entities and entity in message.caption_entities:
        return _get_text_for_entity(message.caption, entity)
    return _get_text_for_entity(message.text or message.caption, entity)


def extract_custom_emojis(message: Message) -> list[tuple[str, str]]:
    """Return unique (default_emoji, custom_emoji_id) pairs from text and captions."""
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
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
async def cmd_start(message: Message) -> None:
    # Always ask language on /start — trilingual prompt so every user understands
    text = (
        "🌐 <b>Choose your language</b> / <b>Выберите язык</b> / <b>Tilni tanlang</b>:\n\n"
        f"{LANGS['en']} — English\n"
        f"{LANGS['ru']} — Русский\n"
        f"{LANGS['uz']} — Oʻzbekcha"
    )
    await message.answer(text, reply_markup=get_lang_keyboard())


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    lang = get_user_lang(message.from_user.id if message.from_user else None, getattr(message.from_user, "language_code", None))
    await message.answer(t("help", lang), reply_markup=get_main_keyboard(lang))


@dp.message(Command("lang"))
async def cmd_lang(message: Message) -> None:
    lang = get_user_lang(message.from_user.id if message.from_user else None, getattr(message.from_user, "language_code", None))
    await message.answer(t("lang_select", lang), reply_markup=get_lang_keyboard())


@dp.message(F.text.in_(BTN_STICKER_ALL))
async def btn_sticker_guide(message: Message) -> None:
    lang = get_user_lang(message.from_user.id if message.from_user else None)
    await message.answer(t("sticker_guide", lang))


@dp.message(F.text.in_(BTN_EMOJI_ALL))
async def btn_emoji_guide(message: Message) -> None:
    lang = get_user_lang(message.from_user.id if message.from_user else None)
    await message.answer(t("emoji_guide", lang))


@dp.message(F.text.in_(BTN_ABOUT_ALL))
async def btn_about(message: Message) -> None:
    lang = get_user_lang(message.from_user.id if message.from_user else None)
    await message.answer(t("about", lang), reply_markup=get_about_keyboard())


@dp.message(F.text.in_(BTN_LANG_ALL))
async def btn_lang(message: Message) -> None:
    lang = get_user_lang(message.from_user.id if message.from_user else None)
    await message.answer(t("lang_select", lang), reply_markup=get_lang_keyboard())





@dp.callback_query(F.data.startswith("lang:"))
async def callback_lang(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user:
        return
    lang = callback.data.split(":", 1)[1]
    if lang not in LANGS:
        return
    set_user_lang(callback.from_user.id, lang)
    try:
        await callback.message.edit_text(t("lang_select", lang), reply_markup=get_lang_keyboard())  # type: ignore
    except Exception:
        pass
    await callback.answer(t("lang_changed", lang))
    # After picking language (especially via /start) immediately show help in that language
    if callback.message:
        await callback.message.answer(t("help", lang), reply_markup=get_main_keyboard(lang))


@dp.message(F.sticker)
async def handle_sticker(message: Message) -> None:
    sticker = message.sticker
    if not sticker:
        return
    lang = get_user_lang(message.from_user.id if message.from_user else None)
    if sticker.is_video:
        kind = t("kind_video", lang)
        icon = "🎬"
    elif sticker.is_animated:
        kind = t("kind_animated", lang)
        icon = "✨"
    elif sticker.type == "custom_emoji":
        kind = t("kind_custom", lang)
        icon = "😀"
    else:
        kind = t("kind_sticker", lang)
        icon = "🎨"

    parts: list[str] = [
        f"<b>{icon} {html.escape(kind)}</b>",
        f"<b>{html.escape(t('label_file_id', lang))}</b>\n{format_ids([sticker.file_id])}",
        f"<b>{html.escape(t('label_unique', lang))}</b>\n{format_ids([sticker.file_unique_id])}",
    ]
    if sticker.set_name:
        parts.append(f"<b>{html.escape(t('label_set', lang))}</b> <code>{html.escape(sticker.set_name)}</code>")
    if sticker.emoji:
        parts.append(f"<b>{html.escape(t('label_emoji', lang))}</b> {html.escape(sticker.emoji)}")
    if getattr(sticker, "custom_emoji_id", None):
        parts.append(f"<b>{html.escape(t('label_custom', lang))}</b>\n{format_ids([sticker.custom_emoji_id])}")

    parts.append(f"<i>{html.escape(t('footer_copy', lang))}</i>")
    await message.reply("\n\n".join(parts))


@dp.message(F.entities | F.caption_entities)
async def handle_custom_emoji(message: Message) -> None:
    emojis = extract_custom_emojis(message)
    if not emojis:
        return
    lang = get_user_lang(message.from_user.id if message.from_user else None)
    # plural not needed per language? Use many vs one
    header_key = "custom_header_many" if len(emojis) > 1 else "custom_header_one"
    header = f"<b>✨ {html.escape(t(header_key, lang))}</b>"
    await message.reply(f"{header}\n{format_custom_emojis(emojis)}")


# Fallback for plain text (not a button, not a custom emoji) — gentle hint, not spammy in groups
@dp.message(F.text)
async def handle_text_fallback(message: Message) -> None:
    if message.chat.type == "private":
        lang = get_user_lang(message.from_user.id if message.from_user else None)
        await message.answer(t("fallback", lang), reply_markup=get_main_keyboard(lang))


async def _health_app() -> None:
    """Tiny aiohttp server for Render health checks (keeps free web service alive)."""
    try:
        from aiohttp import web
    except ImportError:
        logging.warning("aiohttp not installed, health server disabled")
        return
    port = int(os.getenv("PORT", "8080") or "8080")

    async def health(request):  # type: ignore[no-untyped-def]
        return web.Response(text="ok", content_type="text/plain")

    async def root(request):  # type: ignore[no-untyped-def]
        return web.Response(text="idstickbot ok", content_type="text/plain")

    app = web.Application()
    app.router.add_get("/", root)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("Health server listening on 0.0.0.0:%s (Render PORT)", port)
    # Keep alive forever — polling runs alongside
    while True:
        await asyncio.sleep(3600)


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("No token provided. Copy .env.example to .env and set BOT_TOKEN.")
    # Start health server on Render (PORT is set by Render) — polling + HTTP can coexist
    health_task = None
    if os.getenv("PORT"):
        health_task = asyncio.create_task(_health_app())
    async with Bot(
        token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    ) as bot:
        # Set commands for all languages
        try:
            for code in LANGS:
                await bot.set_my_commands(
                    [
                        BotCommand(command="start", description=t("cmd_start", code)),
                        BotCommand(command="help", description=t("cmd_help", code)),
                        BotCommand(command="lang", description=t("cmd_lang", code)),
                    ],
                    language_code=code,
                )
            # Default (no language code) fallback to English
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description=t("cmd_start", "en")),
                    BotCommand(command="help", description=t("cmd_help", "en")),
                    BotCommand(command="lang", description=t("cmd_lang", "en")),
                ]
            )
        except Exception:
            logging.warning("Failed to set bot commands", exc_info=True)

        drop_pending = os.getenv("DROP_PENDING_UPDATES", "false").lower() == "true"
        await bot.delete_webhook(drop_pending_updates=drop_pending)
        try:
            await dp.start_polling(bot, handle_signals=False)
        finally:
            if health_task:
                health_task.cancel()
                try:
                    await health_task
                except asyncio.CancelledError:
                    pass


if __name__ == "__main__":
    asyncio.run(main())
