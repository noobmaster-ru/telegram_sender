"""Фото поста: свежее с карточки ВБ по ссылке из гугл-таблицы, с запасными вариантами.

Ссылка в таблице (колонка G) ведёт на главное фото карточки и не меняется, когда продавец
меняет само фото, поэтому картинку скачиваем заново перед каждой рассылкой.
"""

import io
import logging
import urllib.request
from pathlib import Path

from PIL import Image

import config

logger = logging.getLogger(__name__)

CACHE_DIR = Path("photos_cache")  # на сервере живёт в volume, в git не попадает
DOWNLOAD_TIMEOUT = 20  # секунд
# CDN Wildberries отвечает ошибкой на запросы без браузерного User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def resolve_photo(article: config.Article, image_url: str | None) -> tuple[str, str]:
    """Возвращает (путь к jpg для отправки, источник фото для отчёта).

    1. Ссылка из таблицы есть — скачиваем, конвертируем в jpg (ВБ отдаёт webp, а его Telegram
       отправил бы документом, не фото), кладём в кэш и шлём его.
    2. Скачать не вышло — фото из кэша с прошлой рассылки.
    3. Кэша нет — запасное фото из репозитория (article.image_path).
    """
    cached = CACHE_DIR / f"{article.nm_id}.jpg"

    if image_url:
        try:
            _download_as_jpeg(image_url, cached)
            return str(cached), "с карточки ВБ по ссылке из таблицы"
        except Exception as e:
            logger.warning("⚠️ Не удалось скачать фото для %s (%s): %s", article.label, image_url, e)
    else:
        logger.warning("⚠️ В таблице нет ссылки на фото для %s", article.label)

    if cached.exists():
        return str(cached), "из кэша прошлой рассылки, свежее скачать не удалось"

    return article.image_path, "запасное из репозитория"


def _download_as_jpeg(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:
        data = response.read()

    image = Image.open(io.BytesIO(data)).convert("RGB")  # webp/png с прозрачностью → jpg без неё

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(".tmp")
    image.save(tmp, "JPEG", quality=90)
    tmp.replace(destination)  # атомарно: при обрыве в кэше не остаётся битого файла
