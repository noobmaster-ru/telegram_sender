"""Интерактивный вход на сервере; коды и пароль не пишутся в логи."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config


async def login():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    client = TelegramClient(config.SESSION_NAME, int(os.environ["API_ID"]), os.environ["API_HASH"])
    try:
        await client.start()
        account = await client.get_me()
        if account is None or account.bot:
            raise RuntimeError("Для рассылки нужен пользовательский аккаунт Telegram")
        print("Вход в аккаунт выполнен. Сообщения не отправлялись.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(login())
