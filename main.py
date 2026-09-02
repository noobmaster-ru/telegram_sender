import os
import asyncio
import random
import config as config
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


async def send_report(success, failed):
    """Отправка отчёта о рассылке (без успешных чатов)."""

    timestamp = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S")

    report = (
        f"📊 *Отчёт о рассылке*\n\n"
        f"🕒 Время: {timestamp}\n"
        f"📨 Всего чатов: {len(success) + len(failed)}\n"
        f"✔ Успешно: {len(success)}\n"
        f"❌ Ошибок: {len(failed)}\n\n"
    )

    if failed:
        report += "### ❌ Ошибки:\n"
        for chat, err in failed:
            report += f"• {chat} — `{err}`\n"
    else:
        report += "Ошибок нет 🎉"

    await client.send_message(config.REPORT_CHAT, report, parse_mode="markdown")

async def main(client: TelegramClient):
    logger.info("→ Запуск send.py")
    await client.start()

    with open(config.TARGETS_FILE, "r") as f:
        all_targets = [line.strip() for line in f if line.strip()]

    # Берём случайные SEND_COUNT каналов (если в списке меньше — берём все)
    targets = random.sample(all_targets, min(config.SEND_COUNT, len(all_targets)))

    logger.info(f"📌 Всего каналов: {len(all_targets)}, выбрано случайно: {len(targets)}")

    success = []
    failed = []

    for i, target in enumerate(targets, start=1):
        logger.info(f"\n→ {i}/{len(targets)} отправка в: {target}")

        try:
            await _send_with_flood_retry(target)
            logger.info(f"✔ Успешно → {target}")
            success.append(target)
        except Exception as e:
            logger.error(f"❌ Ошибка для {target}: {e}")
            failed.append((target, str(e)))

        logger.info(f"⏳ sleep {config.SEND_INTERVAL} секунд…")
        await asyncio.sleep(config.SEND_INTERVAL)

    logger.info("\n📤 Отправка отчёта...")
    try:
        await send_report(success, failed)
        logger.info("✔ Отчёт отправлен!")
    except Exception:
        logger.exception("❌ Ошибка при отправке отчёта")
    await client.disconnect()


async def _send_with_flood_retry(target: str, max_flood_retries: int = 2) -> None:
    """Отправка с ожиданием при FloodWait: Telegram сам говорит, сколько ждать."""
    for attempt in range(max_flood_retries + 1):
        try:
            await client.send_file(target, config.IMAGE_PATH, caption=config.CAPTION)
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
