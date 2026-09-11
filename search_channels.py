"""Поиск чатов-кандидатов для рассылки через глобальный поиск Telegram.

Только ищет и печатает список — никуда не вступает и ничего не шлёт.
Запуск на сервере:  docker compose run --rm app uv run python search_channels.py
"""

import asyncio
import logging
import os
import sys

import config
from dotenv import load_dotenv
from telethon import TelegramClient, functions

logging.basicConfig(level=logging.WARNING, handlers=[logging.StreamHandler(sys.stdout)])

QUERIES = [
    "кэшбек за отзыв",
    "кэшбек wb",
    "кэшбек вайлдберриз",
    "выкуп wb",
    "выкупы отзывы",
    "товар за отзыв",
    "товары за отзывы",
    "раздача wb",
    "раздачи товаров",
    "халява wb",
    "бесплатно за отзыв",
    "кэшбек озон",
]


async def main():
    client = TelegramClient(config.SESSION_NAME, os.getenv("API_ID"), os.getenv("API_HASH"))
    await client.start()

    with open(config.TARGETS_FILE) as f:
        already = {line.strip().lstrip("@").lower() for line in f if line.strip()}

    found = {}
    for q in QUERIES:
        try:
            res = await client(functions.contacts.SearchRequest(q=q, limit=50))
        except Exception as e:
            print(f"поиск '{q}' не удался: {e}")
            continue

        for chat in res.chats:
            username = getattr(chat, "username", None)
            if not username or username.lower() in already:
                continue
            if not getattr(chat, "megagroup", False):
                continue  # рассылка работает только в чатах, не в вещательных каналах

            # если обычным участникам запрещено писать — чат нам не подходит
            rights = getattr(chat, "default_banned_rights", None)
            if rights is not None and getattr(rights, "send_messages", False):
                continue

            found[username] = {
                "title": getattr(chat, "title", ""),
                "participants": getattr(chat, "participants_count", 0) or 0,
            }
        await asyncio.sleep(2)  # не частим с поиском

    ranked = sorted(found.items(), key=lambda kv: -kv[1]["participants"])

    print(f"\n=== Кандидаты (чаты с открытой отправкой, ещё не в targets.txt): {len(ranked)} ===")
    for username, info in ranked:
        print(f"@{username}\t{info['participants']}\t{info['title'][:60]}")

    await client.disconnect()


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
