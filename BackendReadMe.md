## README бэкенда

### Обзор
Этот бэкенд — сервис на FastAPI, который отслеживает носимые устройства в автобусах и транслирует актуальный счётчик пассажиров через WebSocket. Используются:
- FastAPI для HTTP- и WebSocket-сервера
- SQLAlchemy и SQLite для хранения данных
- Redis Pub/Sub для трансляции обновлений счётчика в реальном времени (с запасным вариантом в памяти при недоступности Redis)
- Pydantic для валидации запросов

### Структура репозитория (backend)
- `backend/main.py`: инициализация FastAPI-приложения, подключение CORS, жизненный цикл, WebSocket-и и HTML-страница для теста WS.
- `backend/db.py`: настройка SQLAlchemy (движок/сессии) `sqlite:///./data.sqlite3` и зависимость `get_db`.
- `backend/models.py`: ORM-модель `Bus` с полями JSON и полем `count`.
- `backend/redis_client.py`: помощники для Redis (`get_count`, `set_count`, `incr_count`, `decr_count`, `reset_count`, `subscribe_count`) с резервным вариантом в памяти, если Redis недоступен.
- `backend/routers/devices.py`: `POST /devices/event` — добавление/удаление присутствия устройства в автобусе и изменение счётчика.
- `backend/routers/buses.py`: управление автобусами — создание и удаление.
- `backend/requirements.txt`: список зависимостей Python.
- `backend/openapi.json`: снимок схемы OpenAPI.

### Быстрый старт
Требования:
- Python 3.12+
- Redis 7+ (можно запустить через Docker)

Запуск Redis (Docker):
```bash
sudo docker run -d --name redis -p 6379:6379 redis:7-alpine
```

Создание виртуального окружения и установка зависимостей:
```bash
cd backend
python3 -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
```

Запуск сервера (dev):
```bash
uvicorn main:app --reload
```

Альтернатива — запуск из корня репозитория (влияет на путь к файлу SQLite):
```bash
uvicorn backend.main:app --reload
```

Проверка живости:
```bash
curl http://127.0.0.1:8000/health
```

Интерактивная документация: откройте `http://127.0.0.1:8000/docs`

### Конфигурация
- База данных: в `backend/db.py` задано `DATABASE_URL = "sqlite:///./data.sqlite3"`. Путь относителен к текущей рабочей директории. Если вы запускаете из `backend/`, файл БД будет `backend/data.sqlite3`; если из корня (`backend.main:app`), то `data.sqlite3` появится в корне.
- Redis: в `backend/redis_client.py` задано `REDIS_URL = "redis://localhost:6379/0"`. Префикс имени канала Pub/Sub — `bus_count:`, ключ счётчика — `count:{id_bus}`.
- CORS: в dev-разработке разрешены все источники (`allow_origins=["*"]`).

Примечание: указанные значения заданы константами в коде. Для изменения настроек редактируйте `db.py` и `redis_client.py`.

### Модель данных
`Bus` (таблица `bus`):
- `id_bus` (str, PK)
- `devices` (JSON-массив) — произвольные полезные нагрузки устройств, замеченных в автобусе
- `id_devices` (JSON-массив) — список идентификаторов устройств, находящихся в автобусе
- `count` (int) — счётчик пассажиров/устройств (синхронизируется с Redis)

### API эндпоинты
Базовый URL: `http://127.0.0.1:8000`

- POST `/buses`
  - Создать запись автобуса.
  - Тело запроса:
    ```json
    { "id_bus": "42", "initial_count": 0 }
    ```
  - Ответы:
    - 200: `{ "status": "ok", "id_bus": "42", "count": 0 }`
    - 409: `{ "detail": "Bus already exists" }`

- DELETE `/buses/{id_bus}`
  - Удалить автобус и сбросить его счётчик в Redis в 0.
  - Ответы:
    - 200: `{ "status": "ok", "id_bus": "42" }`
    - 404: `{ "detail": "Bus not found" }`

- POST `/devices/event`
  - Добавить или удалить устройство в автобусе. При добавлении счётчик увеличивается; при удалении уменьшается (не опускается ниже 0).
  - Тело запроса:
    ```json
    {
      "id_bus": "42",
      "id_device": "device-123",
      "data": { "rssi": -60, "ts": 1728130000 },
      "flag": true
    }
    ```
    - `flag=true`: добавить устройство, если его ещё нет → сообщение `"added"` (или `"already present"`)
    - `flag=false`: удалить устройство, если оно есть → сообщение `"removed"` (или `"not present"`)
  - Примеры ответов:
    ```json
    { "status": "ok", "message": "added", "count": 5 }
    { "status": "ok", "message": "removed", "count": 4 }
    { "status": "ok", "message": "already present", "count": 5 }
    { "status": "ok", "message": "not present", "count": 4 }
    ```

### WebSocket
- `GET /wb/test` — простая HTML‑страница для проверки WebSocket.
- `WS /ws-echo` — принимает текст и отвечает `echo: <text>`; удобно для быстрой проверки.
- `WS /ws/{id_bus}` — поток JSON‑сообщений с текущим значением счётчика для `id_bus`.
  - При подключении сервер отправляет начальное сообщение:
    ```json
    { "id_bus": "42", "count": 0 }
    ```
  - Далее сообщения приходят при каждом изменении счётчика:
    ```json
    { "id_bus": "42", "count": 1 }
    ```
  - При запущенном Redis обновления доставляются через Pub/Sub всем подписчикам. Без Redis используется резерв в памяти (работает в одном процессе, не распределён).

Быстрая проверка через `websocat`:
```bash
websocat ws://127.0.0.1:8000/ws/42
```

### Примеры cURL
```bash
# Создание автобуса
curl -X POST http://127.0.0.1:8000/buses \
  -H 'Content-Type: application/json' \
  -d '{"id_bus":"42","initial_count":0}'

# Добавление устройства
curl -X POST http://127.0.0.1:8000/devices/event \
  -H 'Content-Type: application/json' \
  -d '{"id_bus":"42","id_device":"device-123","data":{"rssi":-60},"flag":true}'

# Удаление устройства
curl -X POST http://127.0.0.1:8000/devices/event \
  -H 'Content-Type: application/json' \
  -d '{"id_bus":"42","id_device":"device-123","data":{"rssi":-60},"flag":false}'

# Удаление автобуса
curl -X DELETE http://127.0.0.1:8000/buses/42
```

### Заметки и ограничения
- Аутентификация/авторизация не реализованы; эндпоинты открыты (под dev‑нужды).
- CORS разрешает все источники; для продакшена ограничьте список доменов.
- `count` хранится и в SQLite, и в Redis: БД для запросов, Redis — источник событий в реальном времени.
- Без Redis резерв в памяти позволяет локально разрабатывать, но не обеспечивает трансляцию между процессами/инстансами и не переживает перезапуски.

### Диагностика проблем
- Ошибки подключения к Redis: приложение переключится на режим в памяти; для трансляции в реальном времени запустите Redis:
  ```bash
  sudo docker start redis || sudo docker run -d --name redis -p 6379:6379 redis:7-alpine
  ```
- WebSocket шлёт только начальное сообщение: убедитесь, что счётчик меняется (вызовите `/devices/event`) и Redis запущен для мультиклиентской трансляции.
- Путаница с расположением файла SQLite: путь относителен к рабочей директории; выбирайте единый способ запуска (из корня `backend.main:app` или из `backend/` — `main:app`).
- 409 при создании автобуса: уже существует. 404 при удалении: не найден.

### Зависимости
Зафиксированы в `backend/requirements.txt`:
- fastapi 0.114.2
- uvicorn[standard] 0.30.6
- SQLAlchemy 2.0.36
- redis 5.0.8
- pydantic 2.9.2


