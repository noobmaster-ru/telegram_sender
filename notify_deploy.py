"""Уведомление о деплое: отправляет сообщение в REPORT_CHAT.

Запускается сервисом `app` при каждом `docker compose up` (т.е. на каждом деплое).
Рассылку по каналам НЕ делает — только одно сообщение в канал отчётов.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from dotenv import load_dotenv
from telethon import TelegramClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def notify(client: TelegramClient) -> None:
    await client.start()
    timestamp = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y в %H:%M")
    message = f"🚀 **Бот задеплоен на сервере**\n🕒 {timestamp} (МСК)"
    try:
        await client.send_message(config.REPORT_CHAT, message, parse_mode="markdown")
        logger.info("✔ Уведомление о деплое отправлено в %s", config.REPORT_CHAT)
    except Exception:
        logger.exception("❌ Не удалось отправить уведомление о деплое")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    load_dotenv()
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")

    client = TelegramClient(config.SESSION_NAME, API_ID, API_HASH)
    asyncio.run(notify(client=client))
