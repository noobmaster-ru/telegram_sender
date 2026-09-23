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


async def export_chats(
    client: TelegramClient,
    folder_name: str = config.FOLDER_NAME,
    targets_file: str = config.TARGETS_FILE,
) -> list[str] | None:
    """Выгружает чаты папки в targets_file. None — папки нет (файл не трогаем)."""
    logger.info(f"\n=== ЭКСПОРТ ЧАТОВ ИЗ ПАПКИ «{folder_name}» ===")

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

        if folder_title == folder_name:
            folder = f

    logger.info("================================\n")

    if folder is None:
        logger.info(f"❌ Папка '{folder_name}' не найдена!")
        return None

    logger.info(f"✅ Папка найдена → id={folder.id}")

    # закреплённые внутри папки чаты Telegram хранит отдельно от include_peers
    peers = list(getattr(folder, "pinned_peers", None) or []) + list(getattr(folder, "include_peers", None) or [])
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

            if identifier in config.EXCLUDED_TARGETS:
                logger.info("Пропущено (в чёрном списке): %s", identifier)
                continue

            results.append(identifier)
            logger.info("Добавлено: %s", identifier)

        except Exception as e:
            logger.warning("Ошибка получения entity %s: %s", p, e)

    # сохраняем результат
    with open(targets_file, "w") as f:
        for line in results:
            f.write(line + "\n")
    logger.info(f"\n📁 Список успешно сохранён в {targets_file}")
    return results


async def export_all(client: TelegramClient):
    """Ночное обновление: основная папка → targets.txt, папка «1 раз в день» → targets_daily.txt."""
    await export_chats(client)
    # Папку «1 раз» удалили — дневная рассылка должна остановиться, а не слать по старому списку
    daily = await export_chats(client, config.FOLDER_NAME_DAILY, config.TARGETS_FILE_DAILY)
    if daily is None and os.path.exists(config.TARGETS_FILE_DAILY):
        os.remove(config.TARGETS_FILE_DAILY)
        logger.info(f"🗑 {config.TARGETS_FILE_DAILY} удалён: папки «{config.FOLDER_NAME_DAILY}» больше нет")


if __name__ == "__main__":
    load_dotenv()
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    
    client = TelegramClient(config.SESSION_NAME, API_ID, API_HASH)
    asyncio.run(export_all(client=client))