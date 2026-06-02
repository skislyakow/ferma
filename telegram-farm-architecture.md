# Telegram Farm — Архитектура фермы каналов

Моё видение организации фермы на одном VPS.

---

## Вывод: Модульный монолит

**Ни комбайн, ни россыпь проектов.** Оптимум — **единая кодовая база + конфиги по каналам**.

```
/opt/tg-farm/
├── core/                  # Код — один раз, общий для всех
│   ├── parser/
│   ├── translator/
│   ├── publisher/
│   ├── filter/
│   └── db/
│
├── channels/              # Конфиги + данные — каждый канал отдельно
│   ├── crypto/
│   │   ├── .env           # Свои доноры, CPA, бот, язык
│   │   ├── posts.db       # Своя БД
│   │   └── media/         # Свои картинки
│   ├── tech/
│   │   ├── .env
│   │   ├── posts.db
│   │   └── media/
│   ├── finance/
│   │   ├── .env
│   │   ├── posts.db
│   │   └── media/
│   └── auto/
│       ├── .env
│       ├── posts.db
│       └── media/
│
├── manage.py              # Управление фермой
├── scheduler.py           # Планировщик (запускает все каналы)
└── channels.json          # Реестр каналов
```

---

## Почему так, а не иначе?

### ❌ Комбайн (всё в одном процессе)
```
run.py --channel crypto --channel tech --channel finance
```
**Минусы:**
- Ошибка в одном канале валит все
- Разные интервалы публикации (крипте — 30 мин, авто — раз в час) сложно совместить
- CPU/RAM — один процесс жрёт всё сразу
- Трудно отключать каналы по одному

### ❌ Россыпь (папка на канал со своей копией кода)
```
/channel1/ run.py src/
/channel2/ run.py src/
/channel3/ run.py src/
```
**Минусы:**
- Обновлять код в 10 папках — боль
- Диски дублируются (одни и те же .py в 10 копиях)
- Версии разъедутся

### ✅ Модульный монолит
**Плюсы:**
- Код в одном месте → обновил core → обновились все каналы
- Каждый канал — это `.env` + `posts.db`. Меньше 1 МБ на канал
- Один канал сломался → остальные работают
- Асинхронный запуск: все каналы парсятся параллельно
- Легко добавить новый: cp -r template/ channels/new_channel/

---

## Как это работает

### scheduler.py — главный дирижёр
```python
channels = [
    {"name": "crypto",  "interval": 1800},   # каждые 30 мин
    {"name": "tech",    "interval": 3600},   # каждый час
    {"name": "finance", "interval": 7200},   # каждые 2 часа
    {"name": "auto",    "interval": 14400},  # каждые 4 часа
]
while True:
    for ch in channels:
        if time_to_run(ch):
            run_channel(ch["name"])  # отдельный процесс
    time.sleep(60)
```

### Каждый канал исполняется в отдельном процессе
```python
def run_channel(name):
    env_path = f"channels/{name}/.env"
    subprocess.Popen(["python", "core/run.py", env_path])
```

### manage.py — админка фермы
```
python manage.py list           # список каналов + статус
python manage.py start crypto   # запустить один канал
python manage.py stop tech      # остановить
python manage.py logs crypto    # последние логи
python manage.py add new_channel # добавить канал (копирует шаблон)
python manage.py stats          # сводка по всем
```

---

## Ресурсы на VPS ($10/мес)

| Канал | RAM | Диск | CPU |
|-------|-----|------|-----|
| 1 канал | ~30 MB | ~50 MB | 1% |
| 10 каналов | ~300 MB | ~500 MB | 5-10% |
| 25 каналов | ~750 MB | ~1.5 GB | 15-20% |

VPS за $10 (2GB RAM, 20GB SSD, 2 vCPU) тянет **15-20 каналов** без напряга.

---

## Быстрый старт фермы

1. Поднимаешь один канал → отлаживаешь
2. Создаёшь `channels/template/` — `.env`-пустышка
3. `manage.py add crypto` — копия шаблона
4. Правишь `.env` под нишу
5. Повторяешь для tech, finance, auto, health...
6. Запускаешь `scheduler.py` — все каналы крутятся сами

---

## Замеченные баги и фиксы

| Баг | Причина | Фикс |
|-----|---------|------|
| Дубли постов в БД | `hash()` рандомизирован PYTHONHASHSEED | `int(msg_id_str.split("/")[-1])` |
| Процесс умирает | Исключение в цикле | `try/except` вокруг `while True` |
| sendPhoto 400 | caption > 1024 символов | Если текст > 1024 → sendMessage без картинки |
| Футеры в постах | Доноры добавляют "Мы в VK", ссылки | `_clean_footers()` в publisher |
| Посты-тизеры | "читайте на сайте" | `_is_external_source()` в filter |
| Цикл перебирает одно и то же | Отфильтрованные посты не помечались | `mark_skipped()` → published=-1 |
| Screen-сессия без Python-процесса | `bash -c 'cmd'` без экранирования, команда не выполнилась | `PYTHONUNBUFFERED=1 exec venv/bin/python -u ... > log 2>&1` |
| DHCP не выдаёт IP (Timeweb) | Провайдер не назначает IPv4 после переустановки ОС | Сменить провайдера на FirstVDS |
| Пустые bot.log | Буферизация stdout при редиректе в файл | `PYTHONUNBUFFERED=1` + `python -u` |

## Фактический деплой (02.06.2026)

```
FirstVDS (Амстердам) — Ubuntu 24.04 — 1 vCPU, 2 GB RAM, 40 GB NVMe
├── /opt/farm/         # Код (git clone)
├── /opt/farm/start.sh # Стартовый скрипт (screen)
└── /etc/systemd/system/tg-farm.service  # Автозапуск
```

**Управление:**
```bash
ssh root@132.243.121.192
screen -ls                              # список сессий
screen -r crypto                        # логи крипто-канала
screen -r fashion                       # логи модного канала
tail -f /opt/farm/channels/crypto/bot.log
tail -f /opt/farm/channels/fashion/bot.log
cd /opt/farm && git pull && bash start.sh  # обновление
```

## TL;DR

Одна кодовая база `core/` — много конфигов `channels/*/`.
Каждый канал — отдельный процесс. Управление через `manage.py`.
VPS $10 тянет 15-20 каналов.
Новый канал добавляется за 5 минут (скопировать шаблон + настроить .env).
