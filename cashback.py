"""Получение процента кэшбека и цены из гугл-таблицы продавца.

Таблица та же, что подключена к axiomai: первый лист, диапазон C2:K,
где C — процент кэшбека, F — артикул (nm_id), G — ссылка на фото карточки, K — цена на ВБ в рублях.
"""

import logging
import re
from dataclasses import dataclass

import gspread

import config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CashbackData:
    percent: int
    price: int  # цена на ВБ, руб
    source: str  # откуда взяты значения — попадает в отчёт о рассылке
    image_url: str | None = None  # ссылка на фото карточки (колонка G); None — не заполнена или таблица недоступна


def fetch_cashback_data() -> dict[int, CashbackData]:
    """Процент и цена для каждого товара из config.ARTICLES, ключ — nm_id.

    Таблица недоступна — у всех товаров резервные config.FALLBACK_CASHBACK_PERCENT и article.fallback_price.
    Артикул не найден или процент пуст — резерв только у него, остальные из таблицы.
    Найден процент, но не цена — процент из таблицы, цена резервная.
    Ссылка на фото — как есть из таблицы; что с ней делать, решает photos.resolve_photo().
    """
    try:
        percent_by_nm, price_by_nm, image_url_by_nm = _read_sheet()
    except Exception as e:
        logger.warning(
            "⚠️ Не удалось прочитать таблицу (%s): для всех товаров резервные %d%% и цены из config.py",
            e,
            config.FALLBACK_CASHBACK_PERCENT,
        )
        source = f"резервные из config.py, таблица недоступна: {e.__class__.__name__}"
        return {
            article.nm_id: CashbackData(config.FALLBACK_CASHBACK_PERCENT, article.fallback_price, source)
            for article in config.ARTICLES
        }

    result: dict[int, CashbackData] = {}
    for article in config.ARTICLES:
        percent = percent_by_nm.get(article.nm_id)
        if not percent:  # 0 или пусто в таблице считаем «не задан»
            logger.warning(
                "⚠️ Артикул %d (%s) не найден в таблице или процент не заполнен, беру резервные %d%% и %d руб",
                article.nm_id,
                article.label,
                config.FALLBACK_CASHBACK_PERCENT,
                article.fallback_price,
            )
            result[article.nm_id] = CashbackData(
                config.FALLBACK_CASHBACK_PERCENT,
                article.fallback_price,
                "резервные из config.py: артикул не найден в таблице или процент пуст",
            )
            continue

        image_url = image_url_by_nm.get(article.nm_id)
        price = price_by_nm.get(article.nm_id)
        if price:
            result[article.nm_id] = CashbackData(percent, price, "из таблицы", image_url)
        else:
            logger.warning(
                "⚠️ Цена для артикула %d (%s) не заполнена в таблице, беру резервную %d руб",
                article.nm_id,
                article.label,
                article.fallback_price,
            )
            result[article.nm_id] = CashbackData(
                percent, article.fallback_price, "процент из таблицы, цена резервная", image_url
            )

    return result


def _read_sheet() -> tuple[dict[int, int], dict[int, int], dict[int, str]]:
    """(процент, цена, ссылка на фото) по артикулу из первого листа таблицы."""
    gc = gspread.service_account(filename=config.SERVICE_ACCOUNT_FILE)
    rows = gc.open_by_key(config.CASHBACK_TABLE_ID).sheet1.get("C2:K")

    percent_by_nm: dict[int, int] = {}
    price_by_nm: dict[int, int] = {}
    image_url_by_nm: dict[int, str] = {}
    for row in rows:
        if len(row) >= 4 and row[3]:
            try:
                nm_id = int(row[3])
                percent_by_nm[nm_id] = int(row[0]) if row[0] else 0
            except ValueError:
                continue
            if len(row) >= 5 and row[4].strip().startswith("http"):
                image_url_by_nm[nm_id] = row[4].strip()
            if len(row) >= 9 and row[8]:
                # терпим «1249₽», «1 249,50 ₽» и просто числа
                cleaned = re.sub(r"[^\d,.]", "", row[8]).replace(",", ".")
                try:
                    price_by_nm[nm_id] = round(float(cleaned))
                except ValueError:
                    pass

    return percent_by_nm, price_by_nm, image_url_by_nm
