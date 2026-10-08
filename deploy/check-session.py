"""Проверка сохранённой сессии без входа по коду и без отправки сообщений."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config


async def check():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    api_id = os.getenv("API_ID", "")
    api_hash = os.getenv("API_HASH", "")
    if not api_id.isdecimal() or int(api_id) <= 0 or not api_hash:
        raise RuntimeError("Не заполнены API_ID/API_HASH")
    if not Path(f"{config.SESSION_NAME}.session").is_file():
        raise RuntimeError("Файл сессии отправителя отсутствует")
    client = TelegramClient(config.SESSION_NAME, int(api_id), api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Сессия не авторизована; расписание включать нельзя")
        account = await client.get_me()
        if account is None or account.bot:
            raise RuntimeError("Требуется сессия пользовательского аккаунта отправителя")
        print("Telegram доступен; сессия пользовательского аккаунта авторизована.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(check())
