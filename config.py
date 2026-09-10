SESSION_NAME = "sender_session"
TARGETS_FILE = "targets.txt"
IMAGE_PATH = "photo.jpg"
FOLDER_NAME = "Раздачи бесп"
REPORT_CHAT = "@stats_wb_razdachi"     # чат/канал для отчётов
SEND_INTERVAL = 11  # секунд между отправками

USERNAME_BUSINESS_ACCOUNT = "@anna_kryzhovnik"

# --- Кэшбек из гугл-таблицы (та же таблица, что подключена к axiomai) ---
# ид таблицы — из ссылки: docs.google.com/spreadsheets/d/<ВОТ_ЭТА_ЧАСТЬ>/edit
CASHBACK_TABLE_ID = "1ykYRCtKiRxM3R7WH1h1VX6uU0HgxvAfw2e-fPY-daCU"
SERVICE_ACCOUNT_FILE = "sunny-might-477012-c4-bd1e93318fec.json"  # ключ сервисного аккаунта, лежит рядом (в git не попадает)
CASHBACK_NM_IDS = [1223382960, 1192464564]  # артикулы раздачи (дуб, яблоня): процент берём по первому найденному
WB_PRICE = 1600  # резервная цена на ВБ, руб — если в таблице (колонка K) цены нет
FALLBACK_CASHBACK_PERCENT = 20  # если таблица недоступна или артикул не найден

CAPTION_TEMPLATE = """
🔥 Щепа для копчения — КЭШБЕК {percent}%

Набор 4 пакета по 1,5 л — дуб (насыщенный классический дым) или яблоня (мягкий фруктовый аромат). Для коптильни, гриля и мангала: мясо, рыба, птица, сыр.

✅ Чистая древесина, без химии
💰 Цена на ВБ: {price} руб
💸 Вернём {cashback_rub} руб — итог для Вас: {final_price} руб
🎁 Количество мест ограничено

Как получить кэшбек → пишите {username}
""".strip()


def build_caption(percent: int, price: int) -> str:
    cashback_rub = round(price * percent / 100)
    return CAPTION_TEMPLATE.format(
        percent=percent,
        price=price,
        cashback_rub=cashback_rub,
        final_price=price - cashback_rub,
        username=USERNAME_BUSINESS_ACCOUNT,
    )