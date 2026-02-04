import os
import asyncio
import config as config
import logging
import sys
from telethon import TelegramClient
from datetime import datetime
from dotenv import load_dotenv

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

    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

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

    targets = None
    with open(config.TARGETS_FILE, "r") as f:
        targets = [line.strip() for line in f if line.strip()]
        
    logger.info(f"📌 Загружено целей: {len(targets)}")

    success = []
    failed = []

    for i, target in enumerate(targets, start=1):
        logger.info(f"\n→ {i}/{len(targets)} отправка в: {target}")

        try:
            await client.send_file(target, config.IMAGE_PATH, caption=config.CAPTION)
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
    except Exception as e:
        logger.info("❌ Ошибка при отправке отчёта:", e)
    await client.disconnect()


if __name__ == "__main__":
    load_dotenv()
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    
    client = TelegramClient(config.SESSION_NAME, API_ID, API_HASH)
    asyncio.run(main(client=client))
