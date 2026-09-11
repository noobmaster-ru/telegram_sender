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
WB_PRICE = 1450  # резервная цена на ВБ, руб — если в таблице (колонка K) цены нет
FALLBACK_CASHBACK_PERCENT = 20  # если таблица недоступна или артикул не найден

CAPTION_TEMPLATE = """
🔥 ЩЕПА ДЛЯ КОПЧЕНИЯ — {final_price} ₽ ВМЕСТО {price}

Возвращаем {percent}% каждому, кто напишет {username}. Мест мало — разбирают быстро.

📦 В наборе 4 пакета по 1,5 л — хватит на весь сезон
🌳 Дуб — насыщенный классический дым
🍏 Яблоня — мягкий фруктовый аромат
🔥 Для коптильни, гриля и мангала: мясо, рыба, птица, сыр
✅ Чистая древесина, без химии

💰 На ВБ: ~~{price} ₽~~
💸 С кэшбеком: **{final_price} ₽** — {cashback_rub} ₽ возвращаем вам

Как забрать выгоду:
1️⃣ Пишете {username} слово «ЩЕПА»
2️⃣ Покупаете набор на ВБ
3️⃣ Получаете {cashback_rub} ₽ обратно

🎁 Количество мест ограничено — кто написал первым, тот и забрал.

👉 **Жмите → {username}** и забирайте свои {cashback_rub} ₽
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