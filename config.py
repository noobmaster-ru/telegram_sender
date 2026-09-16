from dataclasses import dataclass

SESSION_NAME = "sender_session"
TARGETS_FILE = "targets.txt"

# Каналы, исключённые из рассылки — фильтруются и при экспорте из папки Telegram,
# и при чтении targets.txt (на случай устаревшего файла)
EXCLUDED_TARGETS = {
    "-1002974591139",
}
FOLDER_NAME = "Раздачи бесп"
REPORT_CHAT = "@stats_wb_razdachi"     # чат/канал для отчётов
SEND_INTERVAL = 11  # секунд между отправками
VERIFY_DELAY_MINUTES = 7  # через сколько минут после рассылки проверять, что посты не удалили админы

USERNAME_BUSINESS_ACCOUNT = "@anna_kryzhovnik"

# --- Кэшбек из гугл-таблицы (та же таблица, что подключена к axiomai) ---
# ид таблицы — из ссылки: docs.google.com/spreadsheets/d/<ВОТ_ЭТА_ЧАСТЬ>/edit
CASHBACK_TABLE_ID = "1ykYRCtKiRxM3R7WH1h1VX6uU0HgxvAfw2e-fPY-daCU"
SERVICE_ACCOUNT_FILE = "sunny-might-477012-c4-bd1e93318fec.json"  # ключ сервисного аккаунта, лежит рядом (в git не попадает)
FALLBACK_CASHBACK_PERCENT = 20  # если таблица недоступна или артикул не найден


@dataclass(frozen=True)
class Article:
    """Товар раздачи: по nm_id ищем в таблице процент, цену и ссылку на фото; шаблон подписи свой у каждого."""

    nm_id: int  # артикул на ВБ (колонка F таблицы)
    label: str  # короткое имя для логов и отчёта
    image_path: str  # запасное фото поста: если ссылку из таблицы не удалось скачать и кэша нет (см. photos.py)
    fallback_price: int  # цена на ВБ, руб — если в таблице (колонка K) цены нет
    caption_template: str  # шаблон подписи, плейсхолдеры см. build_caption()


# Плейсхолдеры в шаблонах: {price} — цена на ВБ, {percent} — процент кэшбека,
# {cashback_rub} — сумма возврата, {final_price} — цена с учётом возврата, {username} — бизнес-аккаунт.
# Ключевое слово в каждом посте своё, чтобы бот сразу понимал, какой из двух товаров выбрал клиент.

CAPTION_TEMPLATE_SET_4 = """
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
1️⃣ Пишете {username} слово «ЩЕПА НАБОР»
2️⃣ Покупаете набор на ВБ
3️⃣ Получаете {cashback_rub} ₽ обратно

🎁 Количество мест ограничено — кто написал первым, тот и забрал.

👉 **Жмите → {username}** и забирайте свои {cashback_rub} ₽
""".strip()

CAPTION_TEMPLATE_SINGLE_250 = """
🔥 ЩЕПА ДУБОВАЯ ДЛЯ КОПЧЕНИЯ — {final_price} ₽ ВМЕСТО {price}

Возвращаем {percent}% каждому, кто напишет {username}. Мест мало — разбирают быстро.

📦 Пакет 250 г — хватит на несколько копчений
🌳 Дуб — насыщенный классический дым
🔥 Для коптильни, гриля и мангала: мясо, рыба, птица, сыр
✅ Чистая древесина, без химии

💰 На ВБ: ~~{price} ₽~~
💸 С кэшбеком: **{final_price} ₽** — {cashback_rub} ₽ возвращаем вам

Как забрать выгоду:
1️⃣ Пишете {username} слово «ЩЕПА 250»
2️⃣ Покупаете щепу на ВБ
3️⃣ Получаете {cashback_rub} ₽ обратно

🎁 Количество мест ограничено — кто написал первым, тот и забрал.

👉 **Жмите → {username}** и забирайте свои {cashback_rub} ₽
""".strip()

# Товары раздачи. Посты уходят в каналы поочерёдно: первый канал получает первый товар,
# второй — второй, третий — снова первый и т.д. Порядок каналов каждый раз случайный,
# поэтому за день каждый канал видит оба товара.
ARTICLES = [
    Article(
        nm_id=1223382960,
        label="дуб, набор 4 шт",
        image_path="photo_1223382960.jpg",
        fallback_price=1414,
        caption_template=CAPTION_TEMPLATE_SET_4,
    ),
    Article(
        nm_id=599667749,
        label="дуб, 250 г",
        image_path="photo_599667749.jpg",
        fallback_price=478,
        caption_template=CAPTION_TEMPLATE_SINGLE_250,
    ),
]


def build_caption(article: Article, percent: int, price: int) -> str:
    cashback_rub = round(price * percent / 100)
    return article.caption_template.format(
        percent=percent,
        price=price,
        cashback_rub=cashback_rub,
        final_price=price - cashback_rub,
        username=USERNAME_BUSINESS_ACCOUNT,
    )
