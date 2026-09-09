"""Получение процента кэшбека из гугл-таблицы продавца.

Таблица та же, что подключена к axiomai: первый лист, диапазон C2:J,
где C — процент кэшбека, F — артикул (nm_id).
"""

import logging

import gspread

import config

logger = logging.getLogger(__name__)


def fetch_cashback_percent() -> tuple[int, str]:
    """Возвращает (процент, источник).

    Процент — из таблицы по первому найденному артикулу из config.CASHBACK_NM_IDS.
    При любой ошибке (таблица недоступна, артикул не найден, процент пуст)
    возвращает резервный config.FALLBACK_CASHBACK_PERCENT.
    """
    try:
        gc = gspread.service_account(filename=config.SERVICE_ACCOUNT_FILE)
        rows = gc.open_by_key(config.CASHBACK_TABLE_ID).sheet1.get("C2:J")

        percent_by_nm: dict[int, int] = {}
        for row in rows:
            if len(row) >= 4 and row[3]:
                try:
                    percent_by_nm[int(row[3])] = int(row[0]) if row[0] else 0
                except ValueError:
                    continue

        for nm_id in config.CASHBACK_NM_IDS:
            percent = percent_by_nm.get(nm_id)
            if percent:  # 0 или пусто в таблице считаем «не задан»
                return percent, "из таблицы"

        raise LookupError(f"артикулы {config.CASHBACK_NM_IDS} не найдены в таблице или процент не заполнен")
    except Exception as e:
        logger.warning(
            "⚠️ Не удалось получить кэшбек из таблицы (%s), используем резервный %d%%",
            e,
            config.FALLBACK_CASHBACK_PERCENT,
        )
        return config.FALLBACK_CASHBACK_PERCENT, f"резервный из config.py, таблица недоступна: {e.__class__.__name__}"
