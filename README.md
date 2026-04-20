# GraphOfGod Backend

Отдельный backend-репозиторий на FastAPI для получения связей пользователя VK и построения social graph.

## Архитектура

Весь backend лежит внутри папки `graph_of_god_backend/`.

Структура сделана ближе к промышленной:

- `graph_of_god_backend/main.py` - точка входа для запуска FastAPI
- `graph_of_god_backend/app.py` - фабрика приложения
- `graph_of_god_backend/container.py` - сборка зависимостей backend
- `graph_of_god_backend/core/` - конфиг и базовые backend-ошибки
- `graph_of_god_backend/api/` - HTTP API, роуты и response/request схемы
- `graph_of_god_backend/background/` - фоновые задачи и job manager
- `graph_of_god_backend/modules/vk/` - весь модуль работы с VK API

VK-модуль внутри backend разделен по семантике:

- `auth.py` - получение и кэширование токена
- `client.py` - HTTP-клиент для VK API
- `profile_reference.py` - нормализация входной ссылки/идентификатора
- `entities.py` - доменные сущности VK
- `exceptions.py` - VK-специфичные ошибки
- `friend_links_service.py` - сбор друзей, fallback на подписчиков, обработка приватных профилей
- `social_graph_service.py` - построение графа по нескольким seed-профилям

## Что умеет backend

- принимает профиль VK через HTTP API
- запускает фоновую задачу на сбор данных
- сначала пробует `friends.get`
- если друзей нет, переключается на `users.getFollowers`
- для приватного профиля возвращает пустой `links` и `is_private=true`
- умеет собирать social graph по нескольким профилям VK за один запрос
- добавляет ссылки на аватары пользователей
- ограничивает максимальное число собираемых связей на профиль, чтобы celebrity-аккаунты не зависали на десятки минут
- предоставляет Swagger UI и OpenAPI

## Запуск

Установите зависимости:

```bash
./.venv/bin/pip3 install -r graph_of_god_backend/requirements.txt
```

Скопируйте конфиг:

```bash
cp graph_of_god_backend/.env.example graph_of_god_backend/.env
```

Заполните `.env` одним из вариантов:

```bash
VK_API_TOKEN=your_manual_token
```

или

```bash
VK_APP_ID=12345678
VK_APP_SECRET=your_vk_app_secret
```

Дополнительное важное ограничение:

```bash
VK_MAX_CONNECTIONS_PER_PROFILE=5000
```

Если у профиля больше связей, backend вернет только первые `5000` элементов и пометит ответ флагом `is_truncated=true`.

Запустите backend:

```bash
./.venv/bin/python graph_of_god_backend/main.py
```

Документация:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## API

### Создать задачу

```http
POST /api/v1/friend-links/jobs
Content-Type: application/json

{
  "profile": "https://vk.com/durov"
}
```

### Получить статус задачи

```http
GET /api/v1/friend-links/jobs/{job_id}
```

Возможные значения `source_kind`:

- `friends`
- `followers`
- `private`

Важно для `users.getFollowers`:

- VK отдает подписчиков страницами, максимум по `1000` за вызов
- поэтому backend намеренно режет общий объем результата лимитом `VK_MAX_CONNECTIONS_PER_PROFILE`
- без этого публичные аккаунты вроде `durov` могут парситься очень долго

### Построить social graph

```http
POST /api/v1/social-graphs/jobs?profiles=https://vk.com/durov&profiles=https://vk.com/id1&profiles=vk.com/some_user
```

В Swagger это будет выглядеть как повторяемый параметр `profiles` с кнопкой `Add item`, так что новые профили удобно добавлять и удалять вручную без редактирования JSON body.

Ограничения:

- от 1 до 5 профилей за один запрос
- профили должны быть уникальны после реального разрешения в VK user id

Получение статуса:

```http
GET /api/v1/social-graphs/jobs/{job_id}
```

Результат построен в формате, удобном для графового фронтенда:

- `seed_profiles` - исходные профили, их индексы и их непосредственные связи
- `nodes` - уникальные пользователи графа
- `edges` - рёбра между seed-профилями и найденными связями
- `overlaps` - попарные пересечения между каждым набором seed-профилей
- `stats` - агрегированные счётчики

Ключевая идея ответа такая:

- один пользователь в ответе существует как один `node`
- если этот пользователь встречается у нескольких seed-профилей, в ноде будет `connected_seed_indices`
- для общих друзей фронту не нужно пересчитывать пересечения самостоятельно
- если один из seed-профилей был обрезан лимитом, это будет явно видно по `seed_profiles[].is_truncated` и `stats.truncated_seed_count`

Пример фрагмента ответа:

```json
{
  "seed_profiles": [
    {
      "seed_index": 0,
      "input_profile": "https://vk.com/durov",
      "node_id": "vk:1",
      "user_id": 1,
      "full_name": "Pavel Durov",
      "profile_url": "https://vk.com/durov",
      "avatar_url": "https://...",
      "source_kind": "friends",
      "is_private": false,
      "connection_count": 120,
      "connection_node_ids": ["vk:2", "vk:3"]
    }
  ],
  "nodes": [
    {
      "node_id": "vk:2",
      "user_id": 2,
      "full_name": "Ivan Petrov",
      "profile_url": "https://vk.com/id2",
      "avatar_url": "https://...",
      "is_seed": false,
      "seed_indices": [],
      "connected_seed_indices": [0, 2],
      "shared_seed_count": 2,
      "is_private": false
    }
  ],
  "edges": [
    {
      "edge_id": "edge:1:2",
      "source_node_id": "vk:1",
      "target_node_id": "vk:2",
      "connected_seed_indices": [0]
    }
  ],
  "overlaps": [
    {
      "left_seed_index": 0,
      "right_seed_index": 2,
      "shared_node_ids": ["vk:2"],
      "shared_count": 1
    }
  ],
  "stats": {
    "seed_count": 3,
    "node_count": 48,
    "edge_count": 57,
    "overlap_pair_count": 3,
    "shared_node_count": 6
  }
}
```

## Почему job-based API

Сбор друзей или подписчиков может занимать заметное время, поэтому backend не держит долгий синхронный HTTP-ответ. Вместо этого:

- запрос быстро возвращает `202 Accepted`
- работа уходит в пул потоков
- клиент опрашивает статус задачи отдельным endpoint

Для текущей версии это простой и достаточно надежный способ. Следующий шаг для production-нагрузки - вынос задач в Redis и внешнего worker-процесса.
