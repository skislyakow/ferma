# Ferma — Telegram Channel Farm

Автоматизированная ферма Telegram-каналов для пассивного дохода.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/skislyakow/ferma/blob/master/LICENSE)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-009688?logo=fastapi)
![Telethon](https://img.shields.io/badge/Telethon-1.36.0-2CA5E0?logo=telegram)
![uvicorn](https://img.shields.io/badge/uvicorn-0.34.0-009688)
![feedparser](https://img.shields.io/badge/feedparser-6.0.12-orange)
![Pillow](https://img.shields.io/badge/Pillow-12.2.0-blue)
![requests](https://img.shields.io/badge/requests-2.32.3-green)
![GitHub stars](https://img.shields.io/github/stars/skislyakow/ferma?style=social)
![GitHub forks](https://img.shields.io/github/forks/skislyakow/ferma?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/skislyakow/ferma?style=social)
![Last commit](https://img.shields.io/github/last-commit/skislyakow/ferma)
![Commit activity](https://img.shields.io/github/commit-activity/y/skislyakow/ferma)
![Repo size](https://img.shields.io/github/repo-size/skislyakow/ferma)
![Code size](https://img.shields.io/github/languages/code-size/skislyakow/ferma)
![Platform](https://img.shields.io/badge/Platform-Linux-green)
![Deployment](https://img.shields.io/badge/Deployment-VPS-orange)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)
![mypy](https://img.shields.io/badge/mypy-enabled-blue)

## Каналы

| Канал | Тип | Доноры | Монетизация | Статус |
|-------|-----|--------|-------------|--------|
| @airdrop_crypto_ru | Telegram парсер | @WatcherGuru, @forklog, @CoinTelegraph | CPA | ✅ |
| @fashionmyprofessn | Telegram парсер | 4 донора | CPA | ✅ |
| @yourrepost | Lightning | Telethon + RSS + Reddit + RU каналы | CPA | ✅ |
| Forest | VK-only | r/Forest (Reddit RSS) | — | ✅ |
| Science | VK-only | r/Popular_Science_Ru (Reddit RSS) | — | ✅ |
| Urbanistika | VK-only | r/UrbanHell (Reddit RSS) | — | ✅ |

## Архитектура

```
core/
├── run_channel.py              # Точка входа: парсер → фильтр → перевод → публикация
├── config.py                   # Загрузка .env → dict
├── parser/web_parser.py        # Парсинг t.me/s/ (текст, фото, видео)
├── translator/translator.py    # Yandex Cloud Translate
├── publisher/publisher.py      # Bot API + CPA + watermark + очистка футеров
├── filter/
│   ├── filters.py              # PostFilter: ad/teaser/external/duplicate detection
│   └── manage.py               # load_filters() / save_filters() из filters.json
├── db/database.py              # SQLite (таблица posts, дедупликация)
├── lightning/run_lightning.py  # RE:POST: Telethon + RSS + Reddit + RU + VK crosspost
├── crosspost/vk_poster.py      # VK API: upload_photo, upload_video, post_to_wall
├── admin/server.py             # FastAPI веб-админка (dashboard, каналы, фильтры, логи)
├── forest/run_forest.py        # VK-only: r/Forest → VK
├── science/run_science.py      # VK-only: r/Popular_Science_Ru → VK
└── urbanistika/run_urbanistika.py  # VK-only: r/UrbanHell → VK
```

## Типы каналов

### Telegram парсер (crypto, fashion)
- Парсит `t.me/s/` доноров через `WebParser`
- Фильтрует рекламу, тизеры, дубликаты
- Переводит через Yandex Translate
- Публикует через Bot API с CPA-ссылками

### Lightning / RE:POST (repost)
- Telethon ( userbot) для чтения каналов
- RSS-фиды для breaking news
- Reddit API для видео/фото
- RU-каналы через `t.me/s/` парсер
- VK crosspost (фото + видео)
- Фильтр одиночных ссылок, стоп-слова

### VK-only (forest, science, urbanistika)
- Reddit RSS → VK wall.post
- Без Telegram-пубикации

## Деплой на VPS

```bash
# Клонирование
git clone https://github.com/skislyakow/ferma.git /opt/farm
cd /opt/farm
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Запуск каналов (screen)
screen -dmS admin bash -c 'cd /opt/farm && exec venv/bin/python -u core/admin/server.py'
screen -dmS crypto bash -c 'cd /opt/farm && exec venv/bin/python -u core/run_channel.py channels/crypto/.env'
screen -dmS fashion bash -c 'cd /opt/farm && exec venv/bin/python -u core/run_channel.py channels/fashion/.env'
screen -dmS repost bash -c 'cd /opt/farm && exec venv/bin/python -u core/lightning/run_lightning.py channels/repost/.env'
screen -dmS forest bash -c 'cd /opt/farm && exec venv/bin/python -u core/forest/run_forest.py channels/forest/.env'
screen -dmS science bash -c 'cd /opt/farm && exec venv/bin/python -u core/science/run_science.py channels/science/.env'
screen -dmS urbanistika bash -c 'cd /opt/farm && exec venv/bin/python -u core/urbanistika/run_urbanistika.py channels/urbanistika/.env'
```

## Деплой обновлений

```bash
# На VPS
cd /opt/farm && git pull
rm -f /opt/farm/filters.json  # сброс фильтров к DEFAULT
# Перезапустить изменённые screen-ы
```

## Админка

- Демо (только просмотр): `http://<VPS_IP>:8080/?token=demo`
- Dashboard: общая статистика
- Каналы: CRUD, логи, статус
- Фильтры: редактирование footer_patterns, ad_keywords, external_source_patterns, teaser_patterns

## Окружение

- Python 3.10+ (локально), 3.12 (VPS Ubuntu 24.04)
- Зависимости: `pip install -r requirements.txt`
- Конфиги: `channels/*/.env` (gitignored)
