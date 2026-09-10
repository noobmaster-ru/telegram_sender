"""Получение процента кэшбека и цены из гугл-таблицы продавца.

Таблица та же, что подключена к axiomai: первый лист, диапазон C2:K,
где C — процент кэшбека, F — артикул (nm_id), K — цена на ВБ в рублях.
"""

import logging
import re

import gspread

import config

logger = logging.getLogger(__name__)


def fetch_cashback_data() -> tuple[int, int, str]:
    """Возвращает (процент, цена в рублях, источник).

    Данные — из таблицы по первому найденному артикулу из config.CASHBACK_NM_IDS.
    При любой ошибке (таблица недоступна, артикул не найден, процент пуст)
    возвращает резервные config.FALLBACK_CASHBACK_PERCENT и config.WB_PRICE.
    Если найден процент, но не цена, — процент из таблицы, цена резервная.
    """
    try:
        gc = gspread.service_account(filename=config.SERVICE_ACCOUNT_FILE)
        rows = gc.open_by_key(config.CASHBACK_TABLE_ID).sheet1.get("C2:K")

        percent_by_nm: dict[int, int] = {}
        price_by_nm: dict[int, int] = {}
        for row in rows:
            if len(row) >= 4 and row[3]:
                try:
                    nm_id = int(row[3])
                    percent_by_nm[nm_id] = int(row[0]) if row[0] else 0
                except ValueError:
                    continue
                if len(row) >= 9 and row[8]:
                    # терпим «1249₽», «1 249,50 ₽» и просто числа
                    cleaned = re.sub(r"[^\d,.]", "", row[8]).replace(",", ".")
                    try:
                        price_by_nm[nm_id] = round(float(cleaned))
                    except ValueError:
                        pass

        for nm_id in config.CASHBACK_NM_IDS:
            percent = percent_by_nm.get(nm_id)
            if percent:  # 0 или пусто в таблице считаем «не задан»
                price = price_by_nm.get(nm_id)
                if price:
                    return percent, price, "из таблицы"
                logger.warning("⚠️ Цена для артикула %d не заполнена в таблице, беру резервную %d руб", nm_id, config.WB_PRICE)
                return percent, config.WB_PRICE, "процент из таблицы, цена резервная"

        raise LookupError(f"артикулы {config.CASHBACK_NM_IDS} не найдены в таблице или процент не заполнен")
    except Exception as e:
        logger.warning(
            "⚠️ Не удалось получить кэшбек из таблицы (%s), используем резервные %d%% и %d руб",
            e,
            config.FALLBACK_CASHBACK_PERCENT,
            config.WB_PRICE,
        )
        return (
            config.FALLBACK_CASHBACK_PERCENT,
            config.WB_PRICE,
            f"резервные из config.py, таблица недоступна: {e.__class__.__name__}",
        )
