# VK API Reference (Community & User Tokens)

Compiled from empirical testing. dev.vk.com is a JS SPA, this file replaces it.

## Token Types

### User Token
- Format: `vk1.a.xxx...`
- Obtained via OAuth: `https://oauth.vk.com/authorize?client_id={APP_ID}&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=wall,groups,photos,video,offline&response_type=token&v=5.199`
- Requires **Standalone** app type (not Web, not Community)
- Works with: all methods (unless banned)

### Community Token
- Format: `vk1.a.xxx...` (same format, different type)
- Obtained from group settings → API usage → Access token
- Scopes: "управление сообществом" (group management), "стена", "фотографии", "истории", "файлы", "сообщения сообщества"
- **Limited** — many methods unavailable

## Methods Availability

### ✅ Works with Community Token

| Method | Notes |
|--------|-------|
| `wall.post` | Creates wall posts. `from_group=1` required |
| `stories.getPhotoUploadServer` | Returns upload URL for photo stories |
| `stories.getVideoUploadServer` | Returns upload URL for video stories |
| `stories.save` | Saves uploaded story, returns `video`/`photo` objects |

### ❌ Blocked with Community Token (error 27)

| Method | Error | Notes |
|--------|-------|-------|
| `wall.get` | 27 — Group auth failed | Cannot read wall posts |
| `wall.delete` | 27 — Group auth failed | Cannot delete posts |
| `wall.edit` | 27 — Group auth failed | Cannot edit posts |
| `photos.getWallUploadServer` | 27 — Group auth failed | Cannot upload photos to wall |
| `photos.saveWallPhoto` | 27 — Group auth failed | Cannot save photos to wall |
| `video.save` | 5 — invalid token type | Cannot save/upload videos |
| `docs.getWallUploadServer` | 27 — Group auth failed | Cannot upload docs |
| `apps.get` | 27 — Group auth failed | Cannot get app info |

### ❌ Blocked with User Token (error 5 — banned)

| Method | Error |
|--------|-------|
| Any method | 5 — User authorization failed |

Retry on error 5 is useless — the token/app is banned by VK.

## Working Flows

### Post Photo to Wall (User Token Only)

```
photos.getWallUploadServer(group_id) → upload_url
  ↓ POST photo to upload_url
raw {photo, server, hash}
  ↓
photos.saveWallPhoto(group_id, photo, server, hash)
  ↓ returns [{owner_id, id}]
wall.post(owner_id, message, attachments="photo{owner}_{id}", from_group=1)
```

### Post Video to Wall (User Token Only)

```
video.save(group_id, name, wallpost=0)
  ↓ returns {upload_url}
POST video_file to upload_url
  ↓ returns {video_id, owner_id}
wall.post(owner_id, message, attachments="video{owner}_{id}", from_group=1)
```

### Post Photo via Stories (Community Token — WORKAROUND)

```
stories.getPhotoUploadServer(group_id, add_to_news=1)
  ↓ returns {upload_url}
POST photo to upload_url
  ↓ returns {response: {upload_result}}
stories.save(upload_results)
  ↓ returns {items: [{photo: {owner_id, id}}]}
wall.post(owner_id, message, attachments="photo{owner}_{id}", from_group=1)
```

⚠ This also PUBLISHES a story (visible). To avoid stories, don't use this approach.

### Post Video via Stories (Community Token — WORKAROUND)

```
stories.getVideoUploadServer(group_id)
  ↓ returns {upload_url}
POST video_file to upload_url
  ↓ returns {response: {upload_result}} or {upload_result}
stories.save(upload_results)
  ↓ returns {items: [{video: {owner_id, id, access_key}}]}
wall.post(owner_id, message, attachments="video{owner}_{id}_{access_key}", from_group=1)
```

⚠ This also PUBLISHES a story. Use only if you accept stories being created.

## Retryable Errors

```python
RETRYABLE_CODES = {6, 9, 10}
```

| Code | Meaning | Typical wait |
|------|---------|-------------|
| 6 | Too many requests per second | 1-3s |
| 9 | Flood control (rate limit) | minutes to 24h |
| 10 | Internal server error | retry |

Non-retryable: 5 (auth), 27 (group auth), 14 (captcha), etc.

## Error Codes

| Code | Message | Meaning |
|------|---------|---------|
| 1 | Unknown error | Generic |
| 3 | Unknown method | API method doesn't exist |
| 5 | User authorization failed | Token invalid/revoked/banned |
| 6 | Too many requests | Rate limit per second |
| 9 | Flood control | Rate limit exceeded (longer cooldown) |
| 10 | Internal server error | VK server error |
| 14 | Captcha needed | Need captcha to proceed |
| 15 | Access denied | Token lacks permission |
| 27 | Group auth failed | Method unavailable with community token |
| 214 | Photo size too small | Min dimensions not met |
| 330 | Album not found | Target album doesn't exist |

## Known VK Group IDs

| Channel | Group ID |
|---------|----------|
| repost | 239469377 |
| interesting | 240220784 |
| forest | 239858334 |
| science | 239558545 |
| urbanistika | 239707751 |
