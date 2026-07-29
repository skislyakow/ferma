# VK API Reference

## Token Types

### User Token (полноценный)
- Формат: `vk1.a.xxx...`
- Работает со всеми методами VK API (если аккаунт не забанен)
- Получается через OAuth:

```
https://oauth.vk.com/authorize?client_id={APP_ID}&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=wall,groups,photos,video,offline&response_type=token&v=5.199
```

- Приложение должно быть типа **Standalone** (не Web, не Community)
- Права (scope): `wall` (стена), `groups` (группы), `photos` (фото), `video` (видео), `offline` (бессрочный)

### Community Token (ограниченный)
- Формат: `vk1.a.xxx...` (визуально такой же)
- Получается: Управление сообществом → Настройки → Работа с API → Ключ доступа
- Права: управление сообществом, стена, фотографии, истории, файлы, сообщения сообщества
- **Сильно ограничен** — многие методы недоступны

### Service Token (для некоторых методов)
- Не используется в этом проекте

---

## Авторизация (OAuth)

### Как получить User Token

1. Создать приложение: https://vk.com/apps?act=manage → **Создать приложение**
   - **Название**: любое (например "Ferma")
   - **Тип**: **Standalone** (критически важно! Не Web и не Community)
   - **Платформа**: любая (например "Другое")

2. После создания → ID приложения (app_id)

3. Открыть в браузере:
   ```
   https://oauth.vk.com/authorize?client_id={APP_ID}&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=wall,groups,photos,video,offline&response_type=token&v=5.199
   ```

4. Разрешить доступ → в адресной строке появится:
   ```
   https://oauth.vk.com/blank.html#access_token=vk1.a.xxxxx...&expires_in=86400&user_id=...
   ```
   Извлеки `access_token` (до `&`).

### Если OAuth выдаёт Security Error

| Проблема | Решение |
|----------|---------|
| Приложение не Standalone | Создай новое → тип Standalone |
| redirect_uri не совпадает | Используй `https://oauth.vk.com/blank.html` |
| Приложение заблокировано | Создай новое |
| Аккаунт забанен | Создай новый аккаунт |

### vkhost.github.io (альтернативный сервис)
- Этот сервис упрощает получение токенов, но VK банит страницы за использование сторонних OAuth-клиентов
- Используй официальный OAuth (см. выше) — безопаснее

---

## Error Codes

| Code | Message | Meaning |
|------|---------|---------|
| 1 | Unknown error | Generic |
| 3 | Unknown method | API method doesn't exist |
| 5 | User authorization failed | Token invalid/revoked/banned |
| 6 | Too many requests | Rate limit per second (retryable) |
| 9 | Flood control | Rate limit exceeded — minutes to 24h cooldown (retryable) |
| 10 | Internal server error | VK server error (retryable) |
| 14 | Captcha needed | Need captcha to proceed |
| 15 | Access denied | Token lacks permission |
| 20 | Access to album denied | No access |
| 27 | Group auth failed | Method unavailable with community token |
| 113 | Invalid user id | Wrong user ID |
| 200 | Access to group denied | Not an admin |
| 201 | Access to group denied | Not enough permissions |
| 214 | Photo size too small | Min dimensions not met |
| 330 | Album not found | Target album doesn't exist |
| 921 | Video not found | Video ID doesn't exist |

### Retryable codes
```python
RETRYABLE_CODES = {6, 9, 10}
```
- Error 6: экспоненциальная задержка 1-3с
- Error 9: `retry_after` из ответа VK или exponential backoff
- Error 10: exponential backoff

### НЕ retryable
5 (auth), 27 (group auth), 14 (captcha), 15 (access denied) и др.

---

## Methods & Community Token Availability

### ✅ Доступны с Community Token

| Method | Description |
|--------|-------------|
| `wall.post` | Создание поста на стене; `from_group=1` обязателен |
| `stories.getPhotoUploadServer` | Получить upload_url для загрузки фото в stories |
| `stories.getVideoUploadServer` | Получить upload_url для загрузки видео в stories |
| `stories.save` | Сохранить загруженный медиа-файл, возвращает `{items: [{video/photo: {owner_id, id, access_key}}]}` |

### ❌ Блокированы с Community Token (error 27)

| Method | Error | Notes |
|--------|-------|-------|
| `wall.get` | 27 — Group auth failed | Нельзя читать посты |
| `wall.delete` | 27 — Group auth failed | Нельзя удалять посты |
| `wall.edit` | 27 — Group auth failed | Нельзя редактировать |
| `wall.getById` | 27 — Group auth failed | Нельзя читать по ID |
| `wall.pin` | 27 — Group auth failed | Нельзя закреплять |
| `wall.reportPost` | 27 — Group auth failed | Нельзя жаловаться |
| `wall.postAdsStealth` | 27 — Group auth failed | Нельзя скрытые посты |
| `photos.getWallUploadServer` | 27 — Group auth failed | Нельзя загружать фото на стену |
| `photos.saveWallPhoto` | 27 — Group auth failed | Нельзя сохранять фото |
| `video.save` | 5 — Invalid token type | Нельзя загружать видео |
| `docs.getWallUploadServer` | 27 — Group auth failed | Нельзя загружать документы |
| `groups.getTokenPermissions` | 27 — Group auth failed | Нельзя проверить права токена |
| `apps.get` | 27 — Group auth failed | Нельзя получить инфу о приложении |
| `newsfeed.get` | 27 — Group auth failed | Нельзя читать новости |
| `likes.getList` | 27 — Group auth failed | Нельзя читать лайки |
| `stats.get` | 27 — Group auth failed | Нельзя читать статистику |
| `messages.*` | 27 — Group auth failed | Нельзя сообщения |
| `board.*` | 27 — Group auth failed | Нельзя обсуждения |
| `photos.createAlbum` | 27 — Group auth failed | Нельзя создавать альбомы |
| `photos.saveOwnerPhoto` | 27 — Group auth failed | Нельзя менять аватарку |

---

## Working Flows

### ✅ Post Text to Wall (Работает с обоими токенами)

```
wall.post({
  owner_id: -{group_id},
  message: "текст поста",
  from_group: 1
})
```

### ✅ Post Photo to Wall (Только User Token)

```
photos.getWallUploadServer({group_id})  →  {upload_url}
  ↓ POST photo to upload_url
{photo, server, hash}
  ↓
photos.saveWallPhoto({group_id, photo, server, hash})  →  [{owner_id, id}]
  ↓
wall.post({owner_id, attachments: "photo{owner}_{id}", from_group: 1})
```

### ✅ Post Video to Wall (Только User Token)

```
video.save({group_id, name: "Title", wallpost: 0})  →  {upload_url}
  ↓ POST video_file to upload_url
{video_id, owner_id}
  ↓
wall.post({owner_id, attachments: "video{owner}_{video_id}", from_group: 1})
```

**Параметры `video.save`**:
- `group_id` — ID группы
- `name` — название видео (обязательно)
- `description` — описание (опционально)
- `wallpost` — 0 = не публиковать на стене (мы постим сами)

### ❌ Post Photo via Stories (Community Token — не используем)

```
stories.getPhotoUploadServer({group_id, add_to_news: 1})  →  {upload_url}
  ↓ POST photo to upload_url
{response: {upload_result}}
  ↓
stories.save({upload_results})  →  {items: [{photo: {owner_id, id}}]}
  ↓
wall.post({owner_id, attachments: "photo{owner}_{id}", from_group: 1})
```

⚠ Создаёт видимую историю на странице группы + публикует на стене.

### ❌ Post Video via Stories (Community Token — не используем)

```
stories.getVideoUploadServer({group_id})  →  {upload_url}
  ↓ POST video_file to upload_url
{response: {upload_result}}  или  {upload_result}
  ↓
stories.save({upload_results})  →  {items: [{video: {owner_id, id, access_key}}]}
  ↓
wall.post({owner_id, attachments: "video{owner}_{id}_{access_key}", from_group: 1})
```

⚠ То же — пост + видимая история.

---

## История VK интеграции в проекте (из git log)

| Дата | Коммит | Изменение |
|------|--------|-----------|
| 2026-06-09 | `0113896` | Первый VK crossposter: `vk_poster.py` + `run_vk.py` |
| 2026-06-09 | `4cc0837` | Переписан на Telethon вместо Bot API |
| 2026-06-09 | `6f5cb4b` | VK crosspost inline в `run_lightning.py` (repost) |
| 2026-06-10 | `d66592a` | Strip HTML тегов для VK |
| 2026-06-11 | `249908a` | Footer cleaning для VK такой же как для Telegram |
| 2026-06-13 | `81993f3` | Первый VK-only канал: Popular_Science_Ru |
| 2026-06-19 | `29dfa33` | Urbanistika (r/UrbanHell) |
| 2026-06-25 | `088ccb3` | Forest (r/Forest) |
| 2026-06-30 | `1443b1f` | Видео через `upload_video()` |
| 2026-07-06 | `4a44eee` | Общий рефакторинг, `.env.vk.example` |
| 2026-07-06 | `681cf9c` | Admin panel demo mode |
| 2026-07-12 | `f9b10b9` | Interesting channel отдельно |
| 2026-07-12 | `a7015e2` | Shared `vk_common.py` — `run_cycle()`, `process_entry()` |
| 2026-07-13 | `d994035` | Rate-limit retry (codes 6,9,10) |
| 2026-07-27 | `bbc3c66` | **Бан VK**. Workaround: фото через stories API |
| 2026-07-27 | `49d4a02` | Workaround: стоп-кадр из видео при ошибке загрузки |
| 2026-07-28 | `cea132d` | Видео через stories API, стоп-кадр удалён |
| 2026-07-29 | `3f11e6d` | Stories полностью отключены. Чистый `video.save` + `photos.getWallUploadServer` |

---

## Полный список методов VK API (с archive.org)

Ниже полный список методов VK API v5.131, собранный из web.archive. Разбит по разделам.

### Account
- `account.ban` — забанить пользователя
- `account.changePassword` — сменить пароль (после auth.restore)
- `account.getActiveOffers` — список активных офферов
- `account.getAppPermissions` — права пользователя в приложении
- `account.getBanned` — черный список пользователя
- `account.getCounters` — non-null счётчики
- `account.getInfo` — инфо об аккаунте
- `account.getProfileInfo` — профиль текущего пользователя
- `account.getPushSettings` — настройки push
- `account.registerDevice` — подписать устройство на push
- `account.saveProfileInfo` — редактировать профиль
- `account.setInfo` — редактировать информацию аккаунта
- `account.setNameInMenu` — имя приложения в меню (до 17 символов)
- `account.setOffline` — отметить как offline
- `account.setOnline` — отметить как online на 5 мин
- `account.setPushSettings` — настройки push
- `account.setSilenceMode` — заглушить push на время
- `account.unban` — разбанить
- `account.unregisterDevice` — отписать от push

### Ads
- `ads.addOfficeUsers` — добавить менеджеров/админов рекламного кабинета
- `ads.checkLink` — проверить ссылку рекламы
- `ads.createAds` — создать объявления
- `ads.createCampaigns` — создать кампании
- `ads.createClients` — создать клиентов агентства
- `ads.createLookalikeRequest` — создать look-alike аудиторию
- `ads.createTargetGroup` — создать группу ретаргетинга
- `ads.createTargetPixel` — создать пиксель ретаргетинга
- `ads.deleteAds` — архивировать объявления
- `ads.deleteCampaigns` — архивировать кампании
- `ads.deleteClients` — архивировать клиентов
- `ads.deleteTargetGroup` — удалить группу ретаргетинга
- `ads.deleteTargetPixel` — удалить пиксель
- `ads.getAccounts` — список рекламных кабинетов
- `ads.getAds` — количество/список объявлений
- `ads.getAdsLayout` — описание макетов объявлений
- `ads.getAdsTargeting` — параметры таргетинга
- `ads.getBudget` — бюджет кабинета
- `ads.getCampaigns` — список кампаний
- `ads.getCategories` — категории рекламы
- `ads.getClients` — список клиентов агентства
- `ads.getDemographics` — демография для объявлений/кампаний
- `ads.getFloodStats` — инфо о состоянии счётчика запросов
- `ads.getLookalikeRequests` — список look-alike запросов
- `ads.getMusicians` — список музыкантов
- `ads.getMusiciansByIds` — инфо о музыкантах
- `ads.getOfficeUsers` — менеджеры и супервайзеры кабинета
- `ads.getPostsReach` — охват постов
- `ads.getRejectionReason` — причина отклонения объявления
- `ads.getStatistics` — статистика объявлений/кампаний
- `ads.getSuggestions` — автоподсказки для таргетинга
- `ads.getTargetGroups` — список групп ретаргетинга
- `ads.getTargetPixels` — список пикселей
- `ads.getTargetingStats` — размер аудитории таргетинга + CPC/CPM
- `ads.getUploadURL` — URL для загрузки фото рекламы
- `ads.getVideoUploadURL` — URL для загрузки видео рекламы
- `ads.importTargetContacts` — импорт контактов рекламодателя
- `ads.removeOfficeUsers` — удалить менеджеров/супервайзеров
- `ads.removeTargetContacts` — удалить контакты из группы
- `ads.saveLookalikeRequestResult` — сохранить результат look-alike
- `ads.shareTargetGroup` — поделиться группой ретаргетинга
- `ads.updateAds` — редактировать объявления
- `ads.updateCampaigns` — редактировать кампании
- `ads.updateClients` — редактировать клиентов
- `ads.updateOfficeUsers` — обновить менеджеров
- `ads.updateTargetGroup` — редактировать группу ретаргетинга
- `ads.updateTargetPixel` — обновить пиксель

### App Widgets
- `appWidgets.getAppImageUploadServer` — URL для загрузки фото в коллекцию приложения
- `appWidgets.getAppImages` — коллекция изображений приложения
- `appWidgets.getGroupImageUploadServer` — URL для загрузки фото в коллекцию сообщества
- `appWidgets.getGroupImages` — коллекция изображений сообщества
- `appWidgets.getImagesById` — изображение по ID
- `appWidgets.saveAppImage` — сохранить в коллекцию приложения
- `appWidgets.saveGroupImage` — сохранить в коллекцию сообщества
- `appWidgets.update` — обновить виджет сообщества

### Apps
- `apps.deleteAppRequests` — удалить запросы приложения
- `apps.get` — данные приложения
- `apps.getCatalog` — каталог приложений
- `apps.getFriendsList` — список друзей для инвайтов
- `apps.getLeaderboard` — рейтинг игроков
- `apps.getMiniAppPolicies` — политики mini-app
- `apps.getScopes` — scopes приложения
- `apps.getScore` — счёт пользователя в приложении
- `apps.promoHasActiveGift` — есть ли активный подарок
- `apps.promoUseGift` — использовать подарок
- `apps.sendRequest` — отправить запрос пользователю

### Auth
- `auth.restore` — восстановить доступ через SMS (только для приложений с Direct access)

### Board (Обсуждения)
- `board.addTopic` — создать тему
- `board.closeTopic` — закрыть тему
- `board.createComment` — создать комментарий
- `board.deleteComment` — удалить комментарий
- `board.deleteTopic` — удалить тему
- `board.editComment` — редактировать комментарий
- `board.editTopic` — редактировать заголовок темы
- `board.fixTopic` — закрепить тему
- `board.getComments` — получить комментарии
- `board.getTopics` — получить темы
- `board.openTopic` — открыть тему
- `board.restoreComment` — восстановить комментарий
- `board.unfixTopic` — открепить тему

### Database
- `database.getChairs` — кафедры факультета
- `database.getCities` — города
- `database.getCitiesById` — города по ID
- `database.getCountries` — страны
- `database.getCountriesById` — страны по ID
- `database.getFaculties` — факультеты
- `database.getMetroStations` — станции метро
- `database.getMetroStationsById` — станции метро по ID
- `database.getRegions` — регионы
- `database.getSchoolClasses` — классы школы
- `database.getSchools` — школы
- `database.getUniversities` — ВУЗы

### Docs (Документы)
- `docs.add` — скопировать документ пользователю/сообществу
- `docs.delete` — удалить документ
- `docs.edit` — редактировать документ
- `docs.get` — детальная информация о документах
- `docs.getById` — документы по ID
- `docs.getMessagesUploadServer` — сервер для загрузки документа в сообщения
- `docs.getTypes` — типы документов пользователя
- `docs.getUploadServer` — сервер для загрузки документа
- `docs.getWallUploadServer` — сервер для загрузки документа на стену
- `docs.save` — сохранить документ после загрузки
- `docs.search` — поиск документов

### Donut
- `donut.getFriends` — друзья с доном
- `donut.getSubscription` — подписка пользователя
- `donut.getSubscriptions` — подписчики дон
- `donut.isDon` — проверка донатства

### Execute
- `execute` — универсальный метод для вызова последовательности методов с сохранением промежуточных результатов (VKScript)

### Fave (Закладки)
- `fave.addArticle` — добавить статью
- `fave.addLink` — добавить ссылку
- `fave.addPage` — добавить страницу
- `fave.addPost` — добавить пост
- `fave.addProduct` — добавить товар
- `fave.addTag` — добавить тег
- `fave.addVideo` — добавить видео
- `fave.editTag` — редактировать тег
- `fave.get` — получить закладки
- `fave.getPages` — получить страницы
- `fave.getTags` — получить теги
- `fave.markSeen` — отметить просмотренным
- `fave.removeArticle` — удалить статью
- `fave.removeLink` — удалить ссылку
- `fave.removePage` — удалить страницу
- `fave.removePost` — удалить пост
- `fave.removeProduct` — удалить товар
- `fave.removeTag` — удалить тег
- `fave.removeVideo` — удалить видео
- `fave.reorderTags` — переупорядочить теги
- `fave.setPageTags` — установить теги страницы
- `fave.setTags` — установить теги
- `fave.trackPageInteraction` — отслеживание взаимодействия

### Friends
- `friends.add` — одобрить/создать заявку в друзья
- `friends.addList` — создать список друзей
- `friends.areFriends` — проверить дружбу
- `friends.delete` — отклонить/удалить из друзей
- `friends.deleteAllRequests` — отметить все заявки просмотренными
- `friends.deleteList` — удалить список друзей
- `friends.edit` — редактировать списки друзей пользователя
- `friends.editList` — редактировать список друзей
- `friends.get` — список друзей
- `friends.getAppUsers` — друзья установившие приложение
- `friends.getByPhones` — друзья по телефонам
- `friends.getLists` — списки друзей
- `friends.getMutual` — общие друзья
- `friends.getOnline` — онлайн друзья
- `friends.getRecent` — недавно добавленные друзья
- `friends.getRequests` — входящие/исходящие заявки
- `friends.getSuggestions` — возможные друзья
- `friends.search` — поиск друзей

### Gifts
- `gifts.get` — список подарков пользователя

### Groups (Сообщества)
- `groups.addAddress` — добавить адрес
- `groups.addCallbackServer` — добавить Callback API сервер
- `groups.addLink` — добавить ссылку
- `groups.approveRequest` — одобрить заявку
- `groups.ban` — добавить в черный список
- `groups.create` — создать сообщество
- `groups.deleteAddress` — удалить адрес
- `groups.deleteCallbackServer` — удалить Callback API сервер
- `groups.deleteLink` — удалить ссылку
- `groups.disableOnline` — выключить online
- `groups.edit` — редактировать сообщество
- `groups.editAddress` — редактировать адрес
- `groups.editCallbackServer` — редактировать Callback API сервер
- `groups.editLink` — редактировать ссылку
- `groups.editManager` — добавить/удалить/редактировать руководителя
- `groups.enableOnline` — включить online
- `groups.get` — список сообществ пользователя
- `groups.getAddresses` — адреса
- `groups.getBanned` — черный список
- `groups.getById` — информация о сообществах по ID
- `groups.getCallbackConfirmationCode` — код подтверждения Callback API
- `groups.getCallbackServers` — список Callback API серверов
- `groups.getCallbackSettings` — настройки уведомлений Callback API
- `groups.getCatalog` — каталог сообществ
- `groups.getCatalogInfo` — категории каталога
- `groups.getInvitedUsers` — приглашённые пользователи
- `groups.getInvites` — приглашения в сообщества
- `groups.getLongPollServer` — данные для Bots Long Poll API
- `groups.getLongPollSettings` — настройки Bots Long Poll API
- `groups.getMembers` — участники сообщества
- `groups.getOnlineStatus` — онлайн статус
- `groups.getRequests` — заявки на вступление
- `groups.getSettings` — настройки сообщества
- `groups.getTagList` — список тегов
- `groups.getTokenPermissions` — права токена сообщества
- `groups.invite` — пригласить друзей
- `groups.isMember` — проверка членства
- `groups.join` — вступить в сообщество
- `groups.leave` — покинуть сообщество
- `groups.removeUser` — удалить пользователя
- `groups.reorderLink` — переупорядочить ссылки
- `groups.search` — поиск сообществ
- `groups.setCallbackSettings` — настройки уведомлений Callback API
- `groups.setLongPollSettings` — настройки Bots Long Poll API
- `groups.setSettings` — установить настройки
- `groups.setUserNote` — заметка о пользователе
- `groups.tagAdd` — добавить тег
- `groups.tagBind` — привязать тег
- `groups.tagDelete` — удалить тег
- `groups.tagUpdate` — обновить тег
- `groups.toggleMarket` — включить/выключить магазин
- `groups.unban` — разбанить

### Lead Forms
- `leadForms.create` — создать лид-форму
- `leadForms.delete` — удалить
- `leadForms.get` — получить
- `leadForms.getLeads` — лиды
- `leadForms.getUploadURL` — URL загрузки
- `leadForms.list` — список
- `leadForms.update` — обновить

### Likes
- `likes.add` — добавить лайк
- `likes.delete` — удалить лайк
- `likes.getList` — список лайкнувших
- `likes.isLiked` — проверка лайка

### Market
- `market.add` — добавить товар
- `market.addAlbum` — создать подборку
- `market.addToAlbum` — добавить в подборку
- `market.createComment` — комментарий к товару
- `market.delete` — удалить товар
- `market.deleteAlbum` — удалить подборку
- `market.deleteComment` — удалить комментарий
- `market.edit` — редактировать товар
- `market.editAlbum` — редактировать подборку
- `market.editComment` — редактировать комментарий
- `market.editOrder` — редактировать заказ
- `market.get` — список товаров
- `market.getAlbumById` — данные подборки
- `market.getAlbums` — подборки сообщества
- `market.getById` — товары по ID
- `market.getCategories` — категории
- `market.getComments` — комментарии
- `market.getGroupOrders` — заказы сообщества
- `market.getOrderById` — заказ по ID
- `market.getOrderItems` — товары заказа
- `market.getOrders` — заказы
- `market.removeFromAlbum` — удалить из подборки
- `market.reorderAlbums` — переупорядочить подборки
- `market.reorderItems` — переупорядочить товары
- `market.report` — пожаловаться на товар
- `market.reportComment` — пожаловаться на комментарий
- `market.restore` — восстановить товар
- `market.restoreComment` — восстановить комментарий
- `market.search` — поиск товаров
- `market.searchItems` — поиск по каталогу

### Messages
- `messages.addChatUser` — добавить в чат
- `messages.allowMessagesFromGroup` — разрешить сообщения от сообщества
- `messages.createChat` — создать чат
- `messages.delete` — удалить сообщения
- `messages.deleteChatPhoto` — удалить обложку чата
- `messages.deleteConversation` — удалить переписку
- `messages.denyMessagesFromGroup` — запретить сообщения от сообщества
- `messages.edit` — редактировать сообщение
- `messages.editChat` — редактировать название чата
- `messages.getByConversationMessageId` — сообщение по ID беседы
- `messages.getById` — сообщения по ID
- `messages.getChat` — информация о чате
- `messages.getChatPreview` — превью чата по ссылке
- `messages.getConversationMembers` — участники беседы
- `messages.getConversations` — список бесед
- `messages.getConversationsById` — беседы по ID
- `messages.getHistory` — история сообщений
- `messages.getHistoryAttachments` — медиа из диалога/чата
- `messages.getImportantMessages` — важные сообщения
- `messages.getIntentUsers` — пользователи с намерением
- `messages.getInviteLink` — ссылка для приглашения
- `messages.getLastActivity` — статус и дата последней активности
- `messages.getLongPollHistory` — обновления в личных сообщениях
- `messages.getLongPollServer` — данные для Long Poll
- `messages.isMessagesFromGroupAllowed` — проверка разрешения
- `messages.joinChatByInviteLink` — войти по ссылке
- `messages.markAsAnsweredConversation` — отметить отвеченным
- `messages.markAsImportant` — отметить важным
- `messages.markAsImportantConversation` — отметить беседу важной
- `messages.markAsRead` — отметить прочитанным
- `messages.pin` — закрепить
- `messages.removeChatUser` — удалить из чата
- `messages.restore` — восстановить сообщение
- `messages.search` — поиск сообщений
- `messages.searchConversations` — поиск бесед
- `messages.send` — отправить сообщение
- `messages.sendMessageEventAnswer` — ответ на событие
- `messages.setActivity` — статус печатает
- `messages.setChatPhoto` — установить обложку чата
- `messages.unpin` — открепить

### Newsfeed
- `newsfeed.addBan` — скрыть новости пользователя/сообщества
- `newsfeed.deleteBan` — показать новости
- `newsfeed.deleteList` — удалить список новостей
- `newsfeed.get` — новости пользователя
- `newsfeed.getBanned` — скрытые пользователи/сообщества
- `newsfeed.getComments` — комментарии в новостях
- `newsfeed.getLists` — списки новостей
- `newsfeed.getMentions` — упоминания пользователя
- `newsfeed.getRecommended` — рекомендованные новости
- `newsfeed.getSuggestedSources` — предлагаемые источники
- `newsfeed.ignoreItem` — скрыть элемент
- `newsfeed.saveList` — создать/редактировать список
- `newsfeed.search` — поиск по новостям
- `newsfeed.unignoreItem` — показать скрытое
- `newsfeed.unsubscribe` — отписаться от новостей

### Notes
- `notes.add` — создать заметку
- `notes.createComment` — комментарий
- `notes.delete` — удалить
- `notes.deleteComment` — удалить комментарий
- `notes.edit` — редактировать
- `notes.editComment` — редактировать комментарий
- `notes.get` — заметки пользователя
- `notes.getById` — заметка по ID
- `notes.getComments` — комментарии заметки

### Notifications
- `notifications.get` — уведомления
- `notifications.markAsViewed` — сбросить счётчик
- `notifications.sendMessage` — отправить уведомление

### Orders
- `orders.cancelSubscription` — отменить подписку
- `orders.changeState` — изменить статус
- `orders.get` — список заказов
- `orders.getAmount` — количество
- `orders.getById` — заказ по ID
- `orders.updateSubscription` — обновить подписку

### Pages (Вики-страницы)
- `pages.clearCache` — очистить кеш
- `pages.get` — страница
- `pages.getHistory` — история
- `pages.getTitles` — заголовки
- `pages.getVersion` — версия
- `pages.parse` — парсинг вики-разметки
- `pages.save` — сохранить
- `pages.saveAccess` — сохранить доступ

### Photos
- `photos.confirmTag` — подтвердить метку
- `photos.copy` — скопировать
- `photos.createAlbum` — создать альбом
- `photos.createComment` — комментарий
- `photos.delete` — удалить
- `photos.deleteAlbum` — удалить альбом
- `photos.deleteComment` — удалить комментарий
- `photos.edit` — редактировать
- `photos.editAlbum` — редактировать альбом
- `photos.get` — получить
- `photos.getAlbums` — альбомы
- `photos.getAlbumsCount` — количество альбомов
- `photos.getAll` — все фото
- `photos.getAllComments` — все комментарии
- `photos.getById` — по ID
- `photos.getComments` — комментарии
- `photos.getMarketAlbumUploadServer` — сервер для загрузки в альбом товаров
- `photos.getMarketUploadServer` — сервер для загрузки товара
- `photos.getMessagesUploadServer` — сервер для загрузки в сообщения
- `photos.getNewTags` — новые метки
- `photos.getOwnerCoverPhotoUploadServer` — сервер для обложки
- `photos.getOwnerPhotoUploadServer` — сервер для аватарки
- `photos.getTags` — метки
- `photos.getUploadServer` — сервер для загрузки
- `photos.getUserPhotoUploadServer` — сервер для фото пользователя
- `photos.getWallUploadServer` — сервер для загрузки на стену
- `photos.makeCover` — сделать обложкой
- `photos.move` — переместить
- `photos.putTag` — добавить метку
- `photos.removeTag` — удалить метку
- `photos.reorderAlbums` — переупорядочить альбомы
- `photos.reorderPhotos` — переупорядочить фото
- `photos.report` — пожаловаться
- `photos.reportComment` — пожаловаться на комментарий
- `photos.restore` — восстановить
- `photos.restoreComment` — восстановить комментарий
- `photos.save` — сохранить после загрузки
- `photos.saveMarketAlbumPhoto` — сохранить фото альбома товаров
- `photos.saveMarketPhoto` — сохранить фото товара
- `photos.saveMessagesPhoto` — сохранить фото сообщений
- `photos.saveOwnerCoverPhoto` — сохранить обложку
- `photos.saveOwnerPhoto` — сохранить аватарку
- `photos.saveWallPhoto` — сохранить фото на стену
- `photos.search` — поиск

### Podcasts
- `podcasts.catalog` — каталог подкастов
- `podcasts.catalogBlock` — блок каталога
- `podcasts.chooseFeed` — выбрать фид
- `podcasts.getPopular` — популярные
- `podcasts.getRecentSearchRequests` — недавние поиски
- `podcasts.search` — поиск

### Polls (Опросы)
- `polls.addVote` — голосовать
- `polls.create` — создать
- `polls.deleteVote` — удалить голос
- `polls.edit` — редактировать
- `polls.getById` — по ID
- `polls.getVoters` — голосовавшие

### PrettyCards
- `prettyCards.create` — создать
- `prettyCards.delete` — удалить
- `prettyCards.edit` — редактировать
- `prettyCards.get` — получить
- `prettyCards.getById` — по ID
- `prettyCards.getUploadURL` — URL загрузки
- `prettyCards.list` — список

### Search
- `search.getHints` — подсказки поиска

### Secure
- `secure.addAppEvent` — событие приложения
- `secure.checkToken` — проверить токен
- `secure.getAppBalance` — баланс приложения
- `secure.getSMSHistory` — история SMS
- `secure.getTransactionsHistory` — история транзакций
- `secure.getUserLevel` — уровень пользователя
- `secure.giveEventSticker` — выдать стикер
- `secure.sendNotification` — отправить уведомление
- `secure.sendSMSNotification` — отправить SMS
- `secure.setCounter` — установить счётчик

### Stats
- `stats.get` — статистика
- `stats.getPostReach` — охват поста
- `stats.trackVisitor` — отслеживание посетителей

### Status
- `status.get` — статус
- `status.set` — установить статус

### Storage
- `storage.get` — получить из хранилища
- `storage.getKeys` — ключи
- `storage.set` — сохранить в хранилище

### Stories
- `stories.banOwner` — заблокировать автора
- `stories.delete` — удалить
- `stories.get` — получить
- `stories.getBanned` — заблокированные авторы
- `stories.getById` — по ID
- `stories.getPhotoUploadServer` — URL для загрузки фото
- `stories.getReplies` — ответы
- `stories.getStats` — статистика
- `stories.getVideoUploadServer` — URL для загрузки видео
- `stories.getViewers` — просмотревшие
- `stories.hideAllReplies` — скрыть все ответы
- `stories.hideReply` — скрыть конкретный ответ
- `stories.save` — сохранить
- `stories.search` — поиск
- `stories.unbanOwner` — разбанить автора

### Streaming
- `streaming.getSettings` — настройки Streaming API
- `streaming.getServerUrl` — URL Streaming API сервера
- `streaming.setSettings` — установить настройки

### Users
- `users.get` — информация о пользователях
- `users.getFollowers` — подписчики
- `users.getSubscriptions` — подписки
- `users.report` — пожаловаться
- `users.search` — поиск

### Utils
- `utils.checkLink` — проверка ссылки
- `utils.deleteFromLastShortened` — удалить из последних сокращённых
- `utils.getLastShortenedLinks` — последние сокращённые ссылки
- `utils.getLinkStats` — статистика сокращённой ссылки
- `utils.getServerTime` — время сервера
- `utils.getShortLink` — сократить ссылку
- `utils.resolveScreenName` — разрешить screen_name

### Video
- `video.add` — добавить видео
- `video.addAlbum` — создать альбом
- `video.addToAlbum` — в альбом
- `video.createComment` — комментарий
- `video.delete` — удалить
- `video.deleteAlbum` — удалить альбом
- `video.deleteComment` — удалить комментарий
- `video.edit` — редактировать
- `video.editAlbum` — редактировать альбом
- `video.get` — видео пользователя/сообщества
- `video.getAlbums` — альбомы
- `video.getAlbumsByVideo` — альбомы видео
- `video.getComments` — комментарии
- `video.report` — пожаловаться
- `video.reportComment` — пожаловаться на комментарий
- `video.restore` — восстановить
- `video.restoreComment` — восстановить комментарий
- `video.save` — сохранить (загрузить) видео
- `video.search` — поиск

### Wall
- `wall.checkCopyrightLink` — проверить ссылку на авторские права
- `wall.closeComments` — закрыть комментарии
- `wall.createComment` — комментарий
- `wall.delete` — удалить пост
- `wall.deleteComment` — удалить комментарий
- `wall.edit` — редактировать пост
- `wall.editAdsStealth` — редактировать скрытый пост
- `wall.editComment` — редактировать комментарий
- `wall.get` — список постов на стене
- `wall.getById` — посты по ID
- `wall.getComment` — информация о комментарии
- `wall.getComments` — список комментариев
- `wall.getReposts` — репосты
- `wall.openComments` — открыть комментарии
- `wall.pin` — закрепить пост
- `wall.post` — опубликовать пост
- `wall.postAdsStealth` — скрытый пост (рекламный)
- `wall.reportComment` — пожаловаться на комментарий
- `wall.reportPost` — пожаловаться на пост
- `wall.repost` — репост
- `wall.restore` — восстановить пост
- `wall.restoreComment` — восстановить комментарий
- `wall.search` — поиск по стене
- `wall.unpin` — открепить

---

## VK Group IDs (проект)

| Channel | Group ID | Public URL |
|---------|----------|------------|
| repost | 239469377 | https://vk.com/club239469377 |
| interesting | 240220784 | https://vk.com/club240220784 |
| forest | 239858334 | https://vk.com/club239858334 |
| science | 239558545 | https://vk.com/club239558545 |
| urbanistika | 239707751 | https://vk.com/club239707751 |

---

## Инструкция: Как получить User Token и не получить бан

1. **Создать новый аккаунт VK** (если старый забанен)
   - Номер телефона, почта
   - Подтвердить
   - Войти

2. **Создать приложение**: https://vk.com/apps?act=manage
   - Нажать «Создать приложение»
   - Название: любое
   - Тип: **Standalone** (критически важно!)
   - После создания → скопировать ID приложения

3. **Получить токен**: открыть в браузере ССЫЛКУ ВЫШЕ (с подставленным app_id)
   - Разрешить запрашиваемые права
   - Скопировать токен из адресной строки

4. **Добавить аккаунт в администраторы группы**:
   - VK → Управление сообществом → Участники → Руководители
   - Добавить → новый аккаунт → редактор/администратор

5. **Проверить токен**:
   ```bash
   curl "https://api.vk.com/method/users.get?access_token={TOKEN}&v=5.199"
   ```
   Должно вернуть `{response: [{id, first_name, last_name}]}`

6. **Передать токен** — я обновлю `.env` всех VK-каналов и запущу ферму.

---

## API Versions

Проект использует `v=5.199` (текущая на момент тестирования). VK меняет API раз в несколько месяцев, следить за changelog: https://dev.vk.com/en/api/changelog (JS SPA, открывать в браузере).

Старые версии (5.131, 5.80) всё ещё работают, но без новых фич. Не рекомендуется использовать версии младше 5.100.
