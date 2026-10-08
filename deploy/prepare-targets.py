"""Обновляет основную папку и проверяет непустой список перед включением cron."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import export_folder_chats


async def prepare():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    client = TelegramClient(config.SESSION_NAME, int(os.environ["API_ID"]), os.environ["API_HASH"])
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Сессия не авторизована")
        targets = await export_folder_chats.export_chats(client)
        if not targets:
            raise RuntimeError(f"Папка «{config.FOLDER_NAME}» отсутствует или в ней нет доступных каналов")
        print(f"Подготовлено каналов: {len(targets)}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(prepare())
