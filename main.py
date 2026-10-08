import argparse
import asyncio
import logging
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError

import config
import export_folder_chats


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
    """Пост о Mini App: одинаковое фото и подпись для каналов и отчёта."""

    label: str
    caption: str
    photo: Path


def build_post() -> Post:
    """Проверяет подпись и локальную обложку до подключения к Telegram."""
    caption = config.build_miniapp_caption()
    if not caption.strip():
        raise ValueError("Текст поста о Mini App пуст")
    if len(caption.encode("utf-16-le")) // 2 > 1024:
        raise ValueError("Подпись к фото превышает лимит Telegram: 1024 символа")
    photo = config.MINIAPP_IMAGE_PATH
    if not photo.is_file():
        raise ValueError(f"Обложка поста не найдена: {photo}")
    if not 0 < photo.stat().st_size <= 10 * 1024 * 1024:
        raise ValueError("Обложка поста должна быть непустой и не больше 10 МБ")
    return Post(config.MINIAPP_POST_LABEL, caption, photo)


async def send_post(client: TelegramClient, target: str, post: Post):
    """Отправляет одно фото с короткой подписью и кликабельной ссылкой."""
    return await client.send_file(
        target, str(post.photo), caption=post.caption,
        parse_mode="markdown", force_document=False,
    )


async def send_report(client: TelegramClient, survived, deleted, failed, posts, title="📊 **Отчёт о рассылке**"):
    """Отправка красиво оформленного отчёта о рассылке вместе с самими постами.

    survived — (канал, пост): посты живы спустя VERIFY_DELAY_MINUTES после публикации;
    deleted — (канал, причина, пост): отправились, но были удалены админами/ботами канала;
    failed — (канал, ошибка, пост): не удалось отправить вообще.
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
    lines += [f"🛒 Пост: **{post.label}**" for post in posts]

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

    # То же фото, подпись и параметры отправки, что в каналах
    for post in posts:
        await client.send_message(
            config.REPORT_CHAT, f"👀 **Пост «{post.label}» в этой рассылке:**", parse_mode="markdown"
        )
        await send_post(client, config.REPORT_CHAT, post)

    await client.send_message(config.REPORT_CHAT, "\n".join(lines), parse_mode="markdown")

async def main(client: TelegramClient, daily: bool = False, preview: bool = False):
    """daily=True — рассылка раз в день по папке FOLDER_NAME_DAILY (чаты с лимитом «1 пост в день»)."""
    if daily:
        folder_name, targets_file = config.FOLDER_NAME_DAILY, config.TARGETS_FILE_DAILY
        title = "📊 **Отчёт о рассылке (1 раз в день)**"
    else:
        folder_name, targets_file = config.FOLDER_NAME, config.TARGETS_FILE
        title = "📊 **Отчёт о рассылке**"
    logger.info(f"→ Запуск main.py, папка «{folder_name}»")

    post = build_post()
    try:
        await client.start()
        if preview:
            await send_post(client, config.REPORT_CHAT, post)
            logger.info("✔ Предпросмотр отправлен только в %s", config.REPORT_CHAT)
            return
        await broadcast(client, post, folder_name, targets_file, title)
    finally:
        await client.disconnect()


async def broadcast(client: TelegramClient, post: Post, folder_name: str, targets_file: str, title: str):
    posts = [post]
    # Списка нет (свежий клон после деплоя) — сразу выгружаем его из папки Telegram
    if not os.path.exists(targets_file):
        logger.warning(f"⚠️ {targets_file} отсутствует — обновляю список из папки «{folder_name}»")
        await export_folder_chats.export_chats(client, folder_name, targets_file)
    if not os.path.exists(targets_file):
        logger.warning(f"⚠️ Папки «{folder_name}» нет — рассылать некуда")
        await client.send_message(config.REPORT_CHAT, f"⚠️ Рассылка не запущена: в Telegram нет папки «{folder_name}»")
        return

    with open(targets_file, "r", encoding="utf-8") as f:
        targets = [line.strip() for line in f if line.strip() and line.strip() not in config.EXCLUDED_TARGETS]

    # Шлём во все каналы списка, порядок каждый раз случайный
    random.shuffle(targets)

    logger.info(f"📌 Каналов в рассылке: {len(targets)}, пост: {post.label}")

    sent = []  # (канал, id нашего сообщения, пост) — для проверки на удаление
    failed = []  # (канал, ошибка, пост)

    for i, target in enumerate(targets, start=1):
        logger.info(f"\n→ {i}/{len(targets)} отправка в: {target} — {post.label}")

        try:
            message = await _send_with_flood_retry(client, target, post)
            logger.info(f"✔ Успешно → {target} (message_id={message.id})")
            sent.append((target, message.id, post.label))
        except Exception as e:
            logger.error(f"❌ Ошибка для {target}: {e}")
            failed.append((target, str(e), post.label))

        logger.info(f"⏳ sleep {config.SEND_INTERVAL} секунд…")
        await asyncio.sleep(config.SEND_INTERVAL)

    # Ждём и проверяем, что посты не удалили админы/боты каналов
    logger.info(f"\n⏳ Ждём {config.VERIFY_DELAY_MINUTES} мин перед проверкой постов на удаление…")
    await asyncio.sleep(config.VERIFY_DELAY_MINUTES * 60)
    survived, deleted = await _verify_posts(client, sent)

    logger.info("\n📤 Отправка отчёта...")
    try:
        await send_report(client, survived, deleted, failed, posts, title)
        logger.info("✔ Отчёт отправлен!")
    except Exception:
        logger.exception("❌ Ошибка при отправке отчёта")


async def _verify_posts(client: TelegramClient, sent):
    """Проверяет каждый отправленный пост по его id: жив или удалён.

    Telegram возвращает None вместо сообщения, если оно удалено, — этого
    достаточно, чтобы отличить зачистку админами от нормальной публикации.
    """
    survived = []  # (канал, пост)
    deleted = []  # (канал, причина, пост)

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


async def _send_with_flood_retry(client: TelegramClient, target: str, post: Post, max_flood_retries: int = 2):
    """Отправка с ожиданием при FloodWait: Telegram сам говорит, сколько ждать.

    Возвращает отправленное сообщение — его id нужен для проверки на удаление.
    """
    for attempt in range(max_flood_retries + 1):
        try:
            return await send_post(client, target, post)
        except FloodWaitError as e:
            if attempt == max_flood_retries:
                raise
            wait = e.seconds + 5
            logger.warning(f"⏳ FloodWait для {target}: ждём {wait} секунд (попытка {attempt + 1})")
            await asyncio.sleep(wait)


def cli(argv=None):
    parser = argparse.ArgumentParser(description="Рассылка поста о Mini App «Корзина»")
    parser.add_argument("--daily", action="store_true", help="Использовать папку с лимитом один пост в день")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="Показать подпись и путь к фото локально, без Telegram")
    modes.add_argument("--preview", action="store_true", help="Отправить пост только в канал отчётов")
    args = parser.parse_args(argv)

    if args.dry_run:
        post = build_post()
        print(f"Фото: {post.photo}\n\n{post.caption}")
        return

    load_dotenv(Path(__file__).with_name(".env"))
    api_id = os.getenv("API_ID", "")
    api_hash = os.getenv("API_HASH", "")
    if not api_id.isdecimal() or int(api_id) <= 0 or not api_hash:
        parser.error("Для отправки заполните API_ID и API_HASH в telegram-sender/.env")

    client = TelegramClient(config.SESSION_NAME, int(api_id), api_hash)
    asyncio.run(main(client=client, daily=args.daily, preview=args.preview))


if __name__ == "__main__":
    cli()
