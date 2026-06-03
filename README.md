# Ferma — Telegram Channel Farm

Автоматизированная ферма Telegram-каналов для пассивного дохода.

**Структура:**

```
ferma/
├── core/                      # Общий код
│   ├── run_channel.py         # Запуск одного канала
│   ├── config.py              # Загрузка .env
│   ├── parser/web_parser.py   # Парсер t.me/s/ (текст, фото, видео)
│   ├── translator/translator.py  # Yandex Translate
│   ├── publisher/publisher.py # Bot API (sendMessage, sendPhoto, sendVideo)
│   ├── filter/filters.py      # Антиспам, анти-тизеры, чистка футеров
│   └── db/database.py         # SQLite
│
├── channels/                  # Каналы фермы
│   ├── crypto/                # Крипта
│   ├── fashion/               # Мода
│   └── template/              # Шаблон для нового канала
│
├── manage.py                  # CLI (не используется — screen-ы)
├── requirements.txt
└── README.md
```

## Принцип работы

1. **Парсинг** — забор постов с t.me/s/ доноров (текст + фото + видео)
2. **Фильтрация** — отсев рекламы, тизеров, дубликатов, чистка футеров
3. **Перевод** — Yandex Translate (автоопределение → русский)
4. **Публикация** — Bot API в целевой канал с CPA-ссылками
5. **Очистка** — медиа удаляются с сервера после публикации

## Деплой

```bash
git clone https://github.com/skislyakow/ferma.git /opt/farm
cd /opt/farm
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Запуск канала
PYTHONUNBUFFERED=1 screen -dmS fashion bash -c 'cd /opt/farm && exec venv/bin/python -u core/run_channel.py channels/fashion/.env > channels/fashion/bot.log 2>&1'
```

## Текущие каналы

| Канал | CPA | Интервал |
|-------|-----|----------|
| Крипта | + | 30 мин |
| Мода | — | 30 мин |
