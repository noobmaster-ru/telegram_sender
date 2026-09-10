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


async def send_report(success, failed, percent, price, percent_source, caption):
    """Отправка красиво оформленного отчёта о рассылке вместе с самим постом."""

    timestamp = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y в %H:%M")
    total = len(success) + len(failed)
    rate = round(len(success) / total * 100) if total else 0
    divider = "━━━━━━━━━━━━━━━"

    lines = [
        "📊 **Отчёт о рассылке**",
        divider,
        f"🕒 {timestamp} (МСК)",
        "",
        f"📨 Каналов в рассылке: **{total}**",
        f"✅ Доставлено: **{len(success)}**",
        f"❌ С ошибкой: **{len(failed)}**",
        f"📈 Успешность: **{rate}%**",
        f"💸 Кэшбек в посте: **{percent}%**, цена **{price} руб** ({percent_source})",
    ]

    if success:
        lines += ["", "✅ **Доставлено в:**"]
        lines += [f"   • {chat}" for chat in success]

    if failed:
        lines += ["", "⚠️ **Не доставлено:**"]
        lines += [f"   • {chat} — `{err}`" for chat, err in failed]
    else:
        lines += ["", divider, "🎉 Пост ушёл во все каналы без ошибок!"]

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
        targets = [line.strip() for line in f if line.strip()]

    # Шлём во все каналы списка, порядок каждый раз случайный
    random.shuffle(targets)

    logger.info(f"📌 Каналов в рассылке: {len(targets)}")

    success = []
    failed = []

    for i, target in enumerate(targets, start=1):
        logger.info(f"\n→ {i}/{len(targets)} отправка в: {target}")

        try:
            await _send_with_flood_retry(target, caption)
            logger.info(f"✔ Успешно → {target}")
            success.append(target)
        except Exception as e:
            logger.error(f"❌ Ошибка для {target}: {e}")
            failed.append((target, str(e)))

        logger.info(f"⏳ sleep {config.SEND_INTERVAL} секунд…")
        await asyncio.sleep(config.SEND_INTERVAL)

    logger.info("\n📤 Отправка отчёта...")
    try:
        await send_report(success, failed, percent, price, percent_source, caption)
        logger.info("✔ Отчёт отправлен!")
    except Exception:
        logger.exception("❌ Ошибка при отправке отчёта")
    await client.disconnect()


async def _send_with_flood_retry(target: str, caption: str, max_flood_retries: int = 2) -> None:
    """Отправка с ожиданием при FloodWait: Telegram сам говорит, сколько ждать."""
    for attempt in range(max_flood_retries + 1):
        try:
            await client.send_file(target, config.IMAGE_PATH, caption=caption)
            return
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
