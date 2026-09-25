import os
import asyncio
import random
import cashback
import config as config
import export_folder_chats
import photos
import logging
import sys
from dataclasses import dataclass
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from datetime import datetime
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

def moscow_time(*args):
    return datetime.now(ZoneInfo("Europe/Moscow")).timetuple()

logging.Formatter.converter = moscow_time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Post:
    """Готовый пост одного товара: свежее фото с ВБ и подпись с актуальными суммами."""

    article: config.Article
    percent: int
    price: int
    source: str  # откуда взяты процент и цена — для отчёта
    caption: str
    image_path: str  # что реально отправляем: свежее фото с ВБ, кэш или запасное из репозитория
    image_source: str  # для отчёта


def broadcast_slot() -> int:
    """Номер рассылки за день по config.BROADCAST_HOURS: 7:00 → 0, 12:00 → 1, … (до первой — 0)."""
    hour = datetime.now(ZoneInfo("Europe/Moscow")).hour
    passed = [i for i, h in enumerate(config.BROADCAST_HOURS) if h <= hour]
    return passed[-1] if passed else 0


def build_post() -> Post:
    """Пост товара этой рассылки: N-я рассылка дня — N-й товар по порядку строк таблицы.

    Процент, цену и ссылку на фото тянем из гугл-таблицы перед каждой рассылкой,
    чтобы изменения продавца в таблице и на карточке ВБ сразу попадали в посты.
    Товаров меньше, чем рассылок, — идём по кругу; больше — лишние не попадают ни в одну рассылку.
    """
    data = cashback.fetch_cashback_data()
    articles = {article.nm_id: article for article in config.ARTICLES}
    order = [nm_id for nm_id in data if nm_id in articles]
    slot = broadcast_slot()
    article = articles[order[slot % len(order)]]
    info = data[article.nm_id]
    caption = config.build_caption(article, info.percent, info.price)
    image_path, image_source = photos.resolve_photo(article, info.image_url)
    logger.info(
        f"💸 Рассылка №{slot + 1}: {article.label} — кэшбек {info.percent}%, цена {info.price} руб ({info.source}); "
        f"фото {image_source}"
    )
    return Post(article, info.percent, info.price, info.source, caption, image_path, image_source)


async def send_report(survived, deleted, failed, posts, title="📊 **Отчёт о рассылке**"):
    """Отправка красиво оформленного отчёта о рассылке вместе с самими постами.

    survived — (канал, товар): посты живы спустя VERIFY_DELAY_MINUTES после публикации;
    deleted — (канал, причина, товар): отправились, но были удалены админами/ботами канала;
    failed — (канал, ошибка, товар): не удалось отправить вообще.
    """

    timestamp = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y в %H:%M")
    total = len(survived) + len(deleted) + len(failed)
    rate = round(len(survived) / total * 100) if total else 0
    divider = "━━━━━━━━━━━━━━━"

    lines = [
        title,
        divider,
        f"🕒 {timestamp} (МСК)",
        "",
        f"📨 Каналов в рассылке: **{total}**",
        f"✅ Опубликовано и живо через {config.VERIFY_DELAY_MINUTES} мин: **{len(survived)}**",
        f"🗑 Удалено админами после публикации: **{len(deleted)}**",
        f"❌ Ошибка отправки: **{len(failed)}**",
        f"📈 Успешность: **{rate}%**",
    ]
    lines += [
        f"💸 {post.article.label}: кэшбек **{post.percent}%**, цена **{post.price} руб** ({post.source}), "
        f"фото {post.image_source}"
        for post in posts
    ]

    if survived:
        lines += ["", "✅ **Доставлено в:**"]
        lines += [f"   • {chat} — {label}" for chat, label in survived]

    if deleted:
        lines += ["", "🗑 **Удалено после публикации:**"]
        lines += [f"   • {chat} ({label}) — `{reason}`" for chat, reason, label in deleted]

    if failed:
        lines += ["", "⚠️ **Не доставлено:**"]
        lines += [f"   • {chat} ({label}) — `{err}`" for chat, err, label in failed]

    if not deleted and not failed:
        lines += ["", divider, "🎉 Посты ушли во все каналы и нигде не удалены!"]

    # Сами посты 1-в-1: та же команда, что и для каналов (то же фото, тот же caption)
    for post in posts:
        await client.send_message(
            config.REPORT_CHAT, f"👀 **Пост «{post.article.label}» в этой рассылке:**", parse_mode="markdown"
        )
        await client.send_file(config.REPORT_CHAT, post.image_path, caption=post.caption)

    await client.send_message(config.REPORT_CHAT, "\n".join(lines), parse_mode="markdown")

async def main(client: TelegramClient, daily: bool = False):
    """daily=True — рассылка раз в день по папке FOLDER_NAME_DAILY (чаты с лимитом «1 пост в день»)."""
    if daily:
        folder_name, targets_file = config.FOLDER_NAME_DAILY, config.TARGETS_FILE_DAILY
        title = "📊 **Отчёт о рассылке (1 раз в день)**"
    else:
        folder_name, targets_file = config.FOLDER_NAME, config.TARGETS_FILE
        title = "📊 **Отчёт о рассылке**"
    logger.info(f"→ Запуск send.py, папка «{folder_name}»")

    post = build_post()
    posts = [post]  # для отчёта

    await client.start()

    # Списка нет (свежий клон после деплоя) — сразу выгружаем его из папки Telegram
    if not os.path.exists(targets_file):
        logger.warning(f"⚠️ {targets_file} отсутствует — обновляю список из папки «{folder_name}»")
        await export_folder_chats.export_chats(client, folder_name, targets_file)
    if not os.path.exists(targets_file):
        logger.warning(f"⚠️ Папки «{folder_name}» нет — рассылать некуда")
        await client.send_message(config.REPORT_CHAT, f"⚠️ Рассылка не запущена: в Telegram нет папки «{folder_name}»")
        await client.disconnect()
        return

    with open(targets_file, "r") as f:
        targets = [line.strip() for line in f if line.strip() and line.strip() not in config.EXCLUDED_TARGETS]

    # Шлём во все каналы списка, порядок каждый раз случайный
    random.shuffle(targets)

    logger.info(f"📌 Каналов в рассылке: {len(targets)}, товар: {post.article.label}")

    sent = []  # (канал, id нашего сообщения, товар) — для проверки на удаление
    failed = []  # (канал, ошибка, товар)

    for i, target in enumerate(targets, start=1):
        logger.info(f"\n→ {i}/{len(targets)} отправка в: {target} — {post.article.label}")

        try:
            message = await _send_with_flood_retry(target, post)
            logger.info(f"✔ Успешно → {target} (message_id={message.id})")
            sent.append((target, message.id, post.article.label))
        except Exception as e:
            logger.error(f"❌ Ошибка для {target}: {e}")
            failed.append((target, str(e), post.article.label))

        logger.info(f"⏳ sleep {config.SEND_INTERVAL} секунд…")
        await asyncio.sleep(config.SEND_INTERVAL)

    # Ждём и проверяем, что посты не удалили админы/боты каналов
    logger.info(f"\n⏳ Ждём {config.VERIFY_DELAY_MINUTES} мин перед проверкой постов на удаление…")
    await asyncio.sleep(config.VERIFY_DELAY_MINUTES * 60)
    survived, deleted = await _verify_posts(sent)

    logger.info("\n📤 Отправка отчёта...")
    try:
        await send_report(survived, deleted, failed, posts, title)
        logger.info("✔ Отчёт отправлен!")
    except Exception:
        logger.exception("❌ Ошибка при отправке отчёта")
    await client.disconnect()


async def _verify_posts(sent):
    """Проверяет каждый отправленный пост по его id: жив или удалён.

    Telegram возвращает None вместо сообщения, если оно удалено, — этого
    достаточно, чтобы отличить зачистку админами от нормальной публикации.
    """
    survived = []  # (канал, товар)
    deleted = []  # (канал, причина, товар)

    for target, message_id, label in sent:
        try:
            message = await client.get_messages(target, ids=message_id)
            if message is not None:
                logger.info(f"✔ Пост жив → {target} ({label})")
                survived.append((target, label))
            else:
                logger.warning(f"🗑 Пост удалён → {target} ({label})")
                deleted.append((target, "пост удалён админами/ботом канала", label))
        except Exception as e:
            logger.error(f"❓ Не удалось проверить {target}: {e}")
            deleted.append((target, f"проверка не удалась: {e}", label))

        await asyncio.sleep(1)  # не частим к Telegram

    return survived, deleted


async def _send_with_flood_retry(target: str, post: Post, max_flood_retries: int = 2):
    """Отправка с ожиданием при FloodWait: Telegram сам говорит, сколько ждать.

    Возвращает отправленное сообщение — его id нужен для проверки на удаление.
    """
    for attempt in range(max_flood_retries + 1):
        try:
            return await client.send_file(target, post.image_path, caption=post.caption)
        except FloodWaitError as e:
            if attempt == max_flood_retries:
                raise
            wait = e.seconds + 5
            logger.warning(f"⏳ FloodWait для {target}: ждём {wait} секунд (попытка {attempt + 1})")
            await asyncio.sleep(wait)


if __name__ == "__main__":
    load_dotenv()
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    
    client = TelegramClient(config.SESSION_NAME, API_ID, API_HASH)
    asyncio.run(main(client=client, daily="--daily" in sys.argv[1:]))
