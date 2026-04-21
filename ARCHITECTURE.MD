# GraphOfGod Backend Architecture

## Назначение

`graph_of_god_backend` это отдельный FastAPI backend, который:

- принимает ссылку или идентификатор VK-профиля;
- запускает фоновую задачу на сбор друзей или подписчиков;
- умеет строить social graph для нескольких seed-профилей;
- отдает клиенту job-based API с polling вместо долгого синхронного ответа.

Документ описывает текущее состояние кода. После любого изменения структуры директорий, контрактов API, состава сервисов, схем данных или жизненного цикла задач этот файл нужно перепроверять и дополнять.

## Тип архитектуры

### 1. Модульный layered monolith

Backend организован как модульный монолит с явным разделением на слои:

- `core` - базовая инфраструктура конфигурации и общих исключений;
- `modules` - доменная логика, сейчас основной модуль это интеграция с VK;
- `background` - инфраструктура фоновых задач;
- `api` - HTTP-слой FastAPI и схемы сериализации;
- `container.py` - composition root, где собираются зависимости приложения.

Это не microservices и не hexagonal architecture в строгом виде, но код уже близок к хорошему модульному backend:

- HTTP-роуты тонкие;
- бизнес-логика не живет в роутерах;
- зависимости создаются в одном месте;
- доменные результаты описаны отдельными dataclass-сущностями;
- runtime orchestration явно отделен от VK-логики.

### 2. Job-based API поверх in-memory background manager

Ключевое поведение backend:

- входящий HTTP-запрос не ждет завершения тяжелого VK-сбора;
- backend быстро отвечает `202 Accepted`;
- задача уходит в `ThreadPoolExecutor`;
- клиент потом опрашивает статус по `job_id`.

Это упрощенная локальная архитектура для I/O-bound интеграции с внешним API. Она хорошо подходит для текущей стадии проекта, но имеет ограничения:

- jobs живут только в памяти процесса;
- рестарт процесса сбрасывает состояние всех задач;
- масштабирование на несколько инстансов пока не поддерживается;
- нет очереди, БД и внешнего воркера.

### 3. Composition root и явная сборка зависимостей

Весь runtime wiring собирается в `container.py`. Это правильное решение для текущего масштаба:

- конфиг читается один раз;
- VK client создается один раз;
- сервисы создаются поверх него;
- job managers получают конкретные resolvers;
- shutdown централизован.

## Поток выполнения

### Запуск приложения

1. `main.py` читает `AppConfig`.
2. `main.py` запускает `uvicorn` с уже созданным FastAPI app.
3. `app.py` создает FastAPI application.
4. В `lifespan` вызывается `build_container()`.
5. Контейнер кладется в `app.state.container`.

### Запуск job на friend links

1. Клиент вызывает `POST /api/v1/friend-links/jobs`.
2. Роутер отправляет `profile` в `BackgroundJobManager`.
3. Менеджер создает job со статусом `queued`.
4. В пуле потоков вызывается `FriendLinksService.collect_friend_links`.
5. Сервис:
   - нормализует профиль;
   - делает `users.get`;
   - пытается получить друзей через `friends.get`;
   - при необходимости переключается на `users.getFollowers`;
   - учитывает приватные профили и лимиты.
6. Job сохраняет `succeeded` или `failed`.
7. Клиент читает результат по `GET /api/v1/friend-links/jobs/{job_id}`.

### Запуск job на social graph

1. Клиент вызывает `POST /api/v1/social-graphs/jobs?profiles=...`.
2. Роутер передает список профилей в отдельный `BackgroundJobManager`.
3. В пуле потоков вызывается `SocialGraphService.build_social_graph`.
4. Сервис:
   - валидирует входной список;
   - параллельно собирает `FriendLinksResult` для каждого seed;
   - запрещает дубликаты после реального resolution в `user_id`;
   - ограничивает размер seed-наборов для графа;
   - строит `nodes`, `edges`, `overlaps`, `stats`.
5. Клиент получает результат по `GET /api/v1/social-graphs/jobs/{job_id}`.

## Ключевые архитектурные решения

### Почему HTTP-роуты тонкие

Роутеры здесь не решают доменные задачи. Их роль:

- принять входные данные;
- вызвать нужный manager;
- конвертировать доменные dataclass-результаты в API response models.

Это уменьшает связность и делает доменную логику тестопригодной независимо от FastAPI.

### Почему VK-логика собрана в отдельный модуль

`modules/vk` это фактически bounded context проекта. Внутри модуля разделены:

- аутентификация;
- HTTP-доступ к VK API;
- нормализация входной ссылки;
- доменные сущности;
- VK-специфичные ошибки;
- сервисы friend links и social graph.

Такой разрез правильный: изменения VK API локализуются в одном месте.

### Почему есть отдельные API schema и domain entity

Доменный слой использует dataclass-сущности, а HTTP-слой использует Pydantic-схемы. Это помогает:

- не смешивать внутреннюю модель и внешний API-контракт;
- контролировать сериализацию отдельно;
- не тянуть FastAPI/Pydantic в бизнес-логику.

### Почему здесь нет `requests`, ORM, Celery и Redis

Проект намеренно держится легким:

- HTTP к VK сделан на `urllib`;
- переменные окружения читаются своей небольшой реализацией `dotenv`;
- очереди и persistence пока отсутствуют;
- фоновая обработка сделана стандартной библиотекой.

Это допустимо для локального инструмента и ранней стадии продукта, но не закрывает production-нагрузку.

## Где что лежит

### Корень пакета

- `graph_of_god_backend/` - backend-проект как отдельный Python package.

Ниже перечислены только рабочие исходники и документация. Служебные каталоги вроде `.git`, `__pycache__` и локальный `.env` в архитектурную карту не входят.

## Ответственность по файлам

### Корневые файлы

| Файл | Ответственность |
| --- | --- |
| `ARCHITECTURE.MD` | Архитектурная карта backend. Должна обновляться при структурных изменениях. |
| `.env.example` | Шаблон runtime-конфига backend. Документирует обязательные и опциональные переменные окружения. |
| `README.md` | Краткая пользовательская документация по запуску и API. |
| `requirements.txt` | Минимальный набор Python-зависимостей backend. |
| `__init__.py` | Экспортирует `create_app` как публичную точку входа пакета. |
| `main.py` | CLI entrypoint для локального запуска через `python graph_of_god_backend/main.py`. |
| `app.py` | FastAPI app factory и `lifespan`, где подключается контейнер и shutdown. |
| `container.py` | Composition root: читает конфиг, создает VK client, сервисы и job managers. |

### `core/`

| Файл | Ответственность |
| --- | --- |
| `core/__init__.py` | Маркер core-пакета. |
| `core/config.py` | Чтение и валидация env-конфига backend, включая VK и параметры jobs. |
| `core/dotenv.py` | Маленькая реализация загрузки `.env` без внешней библиотеки. |
| `core/exceptions.py` | Базовые backend-исключения, общие для остальных модулей. |

### `background/`

| Файл | Ответственность |
| --- | --- |
| `background/__init__.py` | Маркер пакета фоновой инфраструктуры. |
| `background/job_manager.py` | Универсальный in-memory manager фоновых jobs на `ThreadPoolExecutor`: submit, get, cleanup, shutdown. |

### `api/`

| Файл | Ответственность |
| --- | --- |
| `api/__init__.py` | Маркер API-пакета. |
| `api/dependencies.py` | FastAPI dependencies для извлечения контейнера и job managers из `app.state`. |
| `api/routers/__init__.py` | Главный `api_router` c `prefix=/api/v1` и регистрацией всех роутеров. |
| `api/routers/health.py` | Простой health endpoint backend. |
| `api/routers/friend_links_jobs.py` | Создание и чтение статуса jobs на сбор связей одного профиля. |
| `api/routers/social_graph_jobs.py` | Создание и чтение статуса jobs на построение social graph. |
| `api/schemas/__init__.py` | Маркер пакета схем. |
| `api/schemas/friend_links.py` | Pydantic response/request models для health и friend-links API. |
| `api/schemas/social_graph.py` | Pydantic response models для social-graph API. |

### `modules/`

| Файл | Ответственность |
| --- | --- |
| `modules/__init__.py` | Маркер business modules. |

### `modules/vk/`

| Файл | Ответственность |
| --- | --- |
| `modules/vk/__init__.py` | Маркер VK-модуля. |
| `modules/vk/auth.py` | Получение access token: либо статического, либо service token через VK OAuth. |
| `modules/vk/client.py` | Низкоуровневый VK API client поверх `urllib`. Выполняет запрос и нормализует ошибки ответа. |
| `modules/vk/entities.py` | Доменные dataclass-сущности: `VKUser`, `FriendLinksResult`, `SocialGraphResult` и связанные структуры. |
| `modules/vk/exceptions.py` | VK-специфичные исключения: ошибки профиля, API, OAuth и формата ответа. |
| `modules/vk/profile_reference.py` | Нормализация входной ссылки, `screen_name` или `id123` в значение, пригодное для `users.get`. |
| `modules/vk/friend_links_service.py` | Основной сервис сбора друзей/подписчиков одного профиля, включая приватность и лимиты. |
| `modules/vk/social_graph_service.py` | Сбор нескольких seed-профилей и построение итогового графа: nodes, edges, overlaps, stats. |

## Ответственность по слоям

### Infrastructure

- `core/config.py`
- `core/dotenv.py`
- `background/job_manager.py`
- `modules/vk/auth.py`
- `modules/vk/client.py`
- `container.py`

Это код, который обеспечивает запуск, конфиг и внешние интеграции.

### Domain

- `modules/vk/entities.py`
- `modules/vk/exceptions.py`
- `modules/vk/profile_reference.py`
- `modules/vk/friend_links_service.py`
- `modules/vk/social_graph_service.py`

Это код, который знает предметную область VK-графа и бизнес-правила.

### Delivery / HTTP

- `app.py`
- `main.py`
- `api/dependencies.py`
- `api/routers/*`
- `api/schemas/*`

Это код, который отдает backend наружу как HTTP API.

## Форматы данных и границы

### Внутренняя доменная модель

Внутри сервисов используются dataclass-сущности из `modules/vk/entities.py`.

Причина:

- они легкие;
- не завязаны на FastAPI;
- удобны для сборки и трансформации данных.

### Внешняя HTTP-модель

Снаружи API отдает Pydantic-модели из `api/schemas`.

Причина:

- это контракт API;
- здесь удобно описывать сериализацию и OpenAPI;
- это изолирует HTTP-формат от внутреннего домена.

## Ограничения текущей архитектуры

### 1. In-memory jobs

Сейчас job manager хранит состояние только в памяти процесса. Это значит:

- нет персистентности;
- после рестарта job теряются;
- горизонтальное масштабирование невозможно без общего хранилища.

### 2. Сильная привязка к VK как единственному доменному модулю

Сейчас весь domain backend фактически равен `modules/vk`. Это нормально для MVP, но если появятся другие источники данных, придется явнее формализовать более общий graph-domain слой.

### 3. Часть аналитики still oriented toward frontend needs

Формат `SocialGraphResult` уже заточен под визуальный frontend. Это удобно, но делает backend менее нейтральным как общий graph-service.

### 4. Нет отдельного persistence слоя

Пока нет:

- БД;
- кэша;
- storage для результатов;
- audit/log storage;
- retry orchestration.

## Что важно проверять при изменениях

После изменения backend-кода этот документ нужно обновить, если меняется хотя бы одно из условий:

- появляется новый роутер;
- меняется структура `api/schemas`;
- меняется состав или wiring контейнера;
- появляются новые фоновые менеджеры или внешние сервисы;
- меняется поток построения `FriendLinksResult` или `SocialGraphResult`;
- добавляются новые модули внутри `modules/`;
- меняются обязательные env-переменные или их семантика.

## Краткая проверка актуальности документа

На момент написания документа backend состоит из:

- одного FastAPI приложения;
- одного composition root;
- одного универсального job manager класса;
- одного доменного модуля `vk`;
- двух основных публичных job API: `friend-links` и `social-graphs`.

Если это описание перестало быть правдой, `ARCHITECTURE.MD` нужно дополнять сразу вместе с кодом.
