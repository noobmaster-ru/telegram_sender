import os
import logging
import sys
import config
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogFiltersRequest



logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def export_chats(client: TelegramClient):
    logger.info("\n=== ЭКСПОРТ ЧАТОВ ИЗ ПАПКИ ===")

    await client.start()

    # Получаем список фильтров Telegram
    filters_obj = await client(GetDialogFiltersRequest())
    filters = getattr(filters_obj, "filters", [])

    folder = None

    logger.info("==== СПИСОК ПАПОК (filters) ====")
    for f in filters:
        # безопасно читаем название
        folder_title = getattr(getattr(f, "title", None), "text", None)

        logger.info(f"type={type(f)}, title={folder_title}")

        if folder_title == config.FOLDER_NAME:
            folder = f

    logger.info("================================\n")

    if folder is None:
        logger.info(f"❌ Папка '{config.FOLDER_NAME}' не найдена!")
        return []

    logger.info(f"✅ Папка найдена → id={folder.id}")

    peers = getattr(folder, "include_peers", [])
    logger.info(f"Найдено объектов: {len(peers)}")

    results = []

    for p in peers:
        try:
            entity = await client.get_entity(p)

            if getattr(entity, "username", None):
                identifier = f"@{entity.username}"
            else:
                raw_id = entity.id
                if str(raw_id).startswith("-100"):
                    identifier = str(raw_id)
                else:
                    identifier = f"-100{raw_id}"

            results.append(identifier)
            logger.info("Добавлено: %s", identifier)

        except Exception as e:
            logger.warning("Ошибка получения entity %s: %s", p, e)

    # сохраняем результат
    with open(config.TARGETS_FILE, "w") as f:
        for line in results:
            f.write(line + "\n")
    logger.info(f"\n📁 Список успешно сохранён в {config.TARGETS_FILE}")
   



if __name__ == "__main__":
    load_dotenv()
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    
    client = TelegramClient(config.SESSION_NAME, API_ID, API_HASH)
    asyncio.run(export_chats(client=client))