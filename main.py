import os
import asyncio
import random
import cashback
import config as config
import export_folder_chats
import logging
import sys
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


async def send_report(survived, deleted, failed, percent, price, percent_source, caption):
    """Отправка красиво оформленного отчёта о рассылке вместе с самим постом.

    survived — посты живы спустя VERIFY_DELAY_MINUTES после публикации;
    deleted — отправились, но были удалены админами/ботами канала;
    failed — не удалось отправить вообще.
    """

    timestamp = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y в %H:%M")
    total = len(survived) + len(deleted) + len(failed)
    rate = round(len(survived) / total * 100) if total else 0
    divider = "━━━━━━━━━━━━━━━"

    lines = [
        "📊 **Отчёт о рассылке**",
        divider,
        f"🕒 {timestamp} (МСК)",
        "",
        f"📨 Каналов в рассылке: **{total}**",
        f"✅ Опубликовано и живо через {config.VERIFY_DELAY_MINUTES} мин: **{len(survived)}**",
        f"🗑 Удалено админами после публикации: **{len(deleted)}**",
        f"❌ Ошибка отправки: **{len(failed)}**",
        f"📈 Успешность: **{rate}%**",
        f"💸 Кэшбек в посте: **{percent}%**, цена **{price} руб** ({percent_source})",
    ]

    if survived:
        lines += ["", "✅ **Доставлено в:**"]
        lines += [f"   • {chat}" for chat in survived]

    if deleted:
        lines += ["", "🗑 **Удалено после публикации:**"]
        lines += [f"   • {chat} — `{reason}`" for chat, reason in deleted]

    if failed:
        lines += ["", "⚠️ **Не доставлено:**"]
        lines += [f"   • {chat} — `{err}`" for chat, err in failed]

    if not deleted and not failed:
        lines += ["", divider, "🎉 Пост ушёл во все каналы и нигде не удалён!"]

    # Сам пост 1-в-1: та же команда, что и для каналов (то же фото, тот же caption)
    await client.send_message(config.REPORT_CHAT, "👀 **Пост в этой рассылке:**", parse_mode="markdown")
    await client.send_file(config.REPORT_CHAT, config.IMAGE_PATH, caption=caption)

    await client.send_message(config.REPORT_CHAT, "\n".join(lines), parse_mode="markdown")

async def main(client: TelegramClient):
    logger.info("→ Запуск send.py")

    # Процент кэшбека и цену тянем из гугл-таблицы перед каждой рассылкой,
    # чтобы изменения продавца в таблице сразу попадали в пост.
    percent, price, percent_source = cashback.fetch_cashback_data()
    caption = config.build_caption(percent, price)
    logger.info(f"💸 Кэшбек в посте: {percent}%, цена {price} руб ({percent_source})")

    await client.start()

    # Списка нет (свежий клон после деплоя) — сразу выгружаем его из папки Telegram
    if not os.path.exists(config.TARGETS_FILE):
        logger.warning("⚠️ targets.txt отсутствует — обновляю список из папки Telegram")
        await export_folder_chats.export_chats(client)

    with open(config.TARGETS_FILE, "r") as f:
        targets = [line.strip() for line in f if line.strip() and line.strip() not in config.EXCLUDED_TARGETS]

    # Шлём во все каналы списка, порядок каждый раз случайный
    random.shuffle(targets)

    logger.info(f"📌 Каналов в рассылке: {len(targets)}")

    sent = []  # (канал, id нашего сообщения) — для проверки на удаление
    failed = []

    for i, target in enumerate(targets, start=1):
        logger.info(f"\n→ {i}/{len(targets)} отправка в: {target}")

        try:
            message = await _send_with_flood_retry(target, caption)
            logger.info(f"✔ Успешно → {target} (message_id={message.id})")
            sent.append((target, message.id))
        except Exception as e:
            logger.error(f"❌ Ошибка для {target}: {e}")
            failed.append((target, str(e)))

        logger.info(f"⏳ sleep {config.SEND_INTERVAL} секунд…")
        await asyncio.sleep(config.SEND_INTERVAL)

    # Ждём и проверяем, что посты не удалили админы/боты каналов
    logger.info(f"\n⏳ Ждём {config.VERIFY_DELAY_MINUTES} мин перед проверкой постов на удаление…")
    await asyncio.sleep(config.VERIFY_DELAY_MINUTES * 60)
    survived, deleted = await _verify_posts(sent)

    logger.info("\n📤 Отправка отчёта...")
    try:
        await send_report(survived, deleted, failed, percent, price, percent_source, caption)
        logger.info("✔ Отчёт отправлен!")
    except Exception:
        logger.exception("❌ Ошибка при отправке отчёта")
    await client.disconnect()


async def _verify_posts(sent):
    """Проверяет каждый отправленный пост по его id: жив или удалён.

    Telegram возвращает None вместо сообщения, если оно удалено, — этого
    достаточно, чтобы отличить зачистку админами от нормальной публикации.
    """
    survived = []
    deleted = []

    for target, message_id in sent:
        try:
            message = await client.get_messages(target, ids=message_id)
            if message is not None:
                logger.info(f"✔ Пост жив → {target}")
                survived.append(target)
            else:
                logger.warning(f"🗑 Пост удалён → {target}")
                deleted.append((target, "пост удалён админами/ботом канала"))
        except Exception as e:
            logger.error(f"❓ Не удалось проверить {target}: {e}")
            deleted.append((target, f"проверка не удалась: {e}"))

        await asyncio.sleep(1)  # не частим к Telegram

    return survived, deleted


async def _send_with_flood_retry(target: str, caption: str, max_flood_retries: int = 2):
    """Отправка с ожиданием при FloodWait: Telegram сам говорит, сколько ждать.

    Возвращает отправленное сообщение — его id нужен для проверки на удаление.
    """
    for attempt in range(max_flood_retries + 1):
        try:
            return await client.send_file(target, config.IMAGE_PATH, caption=caption)
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
    asyncio.run(main(client=client))
