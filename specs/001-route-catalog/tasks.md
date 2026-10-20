# Задачі: каталог туристичних маршрутів вихідного дня

**Фаза:** tasks (до коду сервісу)
**Дата:** 2026-10-20
**Специфікація:** [spec.md](spec.md) | **План:** [plan.md](plan.md)

Кожна задача має прив'язку до критерію приймання (AC) зі специфікації. Задачі
впорядковані так, щоб кожен наступний крок спирався на завершений попередній.
Задачі позначачені `[ ]` і змінюються на `[X]` у міру виконання.

---

## Блок 1. Моделі даних (T001–T004)

| ID | Задача | Файл | AC | Статус |
|---|---|---|---|---|
| T001 | `RouteCreate`: 4 поля, `distance_km` 0.5–100.0, `duration_hours` 0.5–24.0, `difficulty` з переліку, `name` 3–80 символів. Поля `id`/`created_at` відсутні — клієнт їх не передає | `app/models.py` | AC1, AC3 | [ ] |
| T002 | `Route`: вихідна модель з `id`, `created_at` та чотирма полями | `app/models.py` | AC1 | [ ] |
| T003 | `RouteList`: `items: list[Route]`, `count: int` | `app/models.py` | AC2 | [ ] |
| T004 | Тіла помилок зі змістовим `status`: `needs_clarification` (з `missing`, `questions`), `rejected` (з `reason`), `model_unavailable` (з `reason`) | `app/models.py` | AC5, AC6, AC7, AC8 | [ ] |

## Блок 2. Правила застосунку (T005–T009)

| ID | Задача | Файл | AC | Статус |
|---|---|---|---|---|
| T005 | `validate_proposal(proposal, source_text)`: **структура** — усі 4 ключі, числа — числа, `difficulty` — рядок; порушення → `rejected(invalid_structure)` | `app/policy.py` | AC6 | [ ] |
| T006 | **Повнота**: поле `null` → `needs_clarification` зі списком відсутніх; `record` не формується | `app/policy.py` | AC5 | [ ] |
| T007 | **Діапазон і перелік**: числа в межах, `difficulty` ∈ {easy, medium, hard}; порушення → `rejected(invalid_semantics)` | `app/policy.py` | AC7 | [ ] |
| T008 | **Звірка числа з текстом**: `distance_km` і `duration_hours` мають зустрічатися в тексті повідомлення (з допуском на округлення цілого); порушення → `rejected(invalid_semantics)` | `app/policy.py` | AC7 | [ ] |
| T009 | `normalize_name`: відкидає службове слово перед назвою («Маршрут Соколиця» → «Соколиця»); `questions_for(missing)` — питання до автора за відсутніми полями | `app/policy.py` | AC4, AC5 | [ ] |

## Блок 3. Сховище (T010–T012)

| ID | Задача | Файл | AC | Статус |
|---|---|---|---|---|
| T010 | `RouteStore(path)`: читання JSON-файлу; відсутність файлу = порожній каталог; `add()` повертає запис із наступним `id` | `app/storage.py` | AC1, AC2 | [ ] |
| T011 | `created_at` у UTC з часовою зоною; `id` починається з 1 і не перевикористовується | `app/storage.py` | AC1 | [ ] |
| T012 | Шлях сховища з `ROUTES_DB` (типово `data/routes.json`); запис через тимчасовий файл + перейменування | `app/storage.py` | AC2 | [ ] |

## Блок 4. AI-компонент (T013–T017)

| ID | Задача | Файл | AC | Статус |
|---|---|---|---|---|
| T013 | Протокол `Proposer.propose(text) -> dict \| None` | `app/ai.py` | AC4 | [ ] |
| T014 | `LLMProposer`: живий виклик через OpenAI-сумісний клієнт; іменовані стани збою (`timeout`, `rate_limited`, `provider_unavailable`, `invalid_structure`, `incomplete`); retry до 3 спроб | `app/ai.py` | AC8, AC9 | [ ] |
| T015 | `StubProposer`: відповідь із `ROUTE_LLM_STUB` за **точним** текстом запиту; відсутність збігу → `invalid_structure` | `app/ai.py` | AC4, AC6, AC7 | [ ] |
| T016 | `OfflineProposer`: імітує `provider_unavailable` | `app/ai.py` | AC8 | [ ] |
| T017 | `get_proposer()`: вибір реалізації за `ROUTE_LLM_MODE` (`live`/`stub`/`offline`). **Модуль не імпортує `app.storage`** | `app/ai.py` | AC9 | [ ] |

## Блок 5. Сервісний шар (T018–T020)

| ID | Задача | Файл | AC | Статус |
|---|---|---|---|---|
| T018 | `create_route(data, store)` — ручне створення, **без моделі** | `app/service.py` | AC1 | [ ] |
| T019 | `list_routes(store)` — список у порядку зростання `id` | `app/service.py` | AC2 | [ ] |
| T020 | `create_route_from_text(text, proposer, store)` — виклик провайдера, перевірка пропозиції, запис **лише** при `complete` | `app/service.py` | AC4, AC5, AC6, AC7, AC8 | [ ] |

## Блок 6. HTTP-шар (T021–T026)

| ID | Задача | Файл | AC | Статус |
|---|---|---|---|---|
| T021 | `POST /routes` → `201` зі створеним записом; помилка входу → `422`; сховище не змінюється | `app/main.py` | AC1, AC3 | [ ] |
| T022 | `GET /routes` → `200` з `{"items": [...], "count": N}` | `app/main.py` | AC2 | [ ] |
| T023 | `POST /routes/from-text`: межа `text` 1–2000 символів → `422` **без виклику моделі** | `app/main.py` | AC4 | [ ] |
| T024 | Мапінг статусів на HTTP: `complete` → `201`; `needs_clarification` → `422` + `status`; `rejected` → `422` + `status` + `reason`; `model_unavailable` → `503` + `status` | `app/main.py` | AC5, AC6, AC7, AC8 | [ ] |
| T025 | Залежність `get_proposer` через `Depends` — щоб тести підміняли провайдера без зміни звичайного API | `app/main.py` | AC9 | [ ] |
| T026 | **Жодного параметра обходу** в публічному API: режим підміни визначається лише процесом сервісу | `app/main.py` | AC9 | [ ] |

## Блок 7. Автоматичні тести (T027–T036)

| ID | Задача | Файл | AC | Статус |
|---|---|---|---|---|
| T027 | Fixtures: `TestClient` із тимчасовим сховищем; підміна `get_proposer`; ізольований `ROUTES_DB` | `tests/conftest.py` | AC1–AC8 | [ ] |
| T028 | `test_manual_create_creates_visible_record`: `201`, поля, `id` є в наступному списку, `count` +1 | `tests/test_routes.py` | AC1 | [ ] |
| T029 | `test_list_returns_items_and_count`: `200`, `items` — масив, `count == len(items)`; порожнє сховище → `count = 0` | `tests/test_routes.py` | AC2 | [ ] |
| T030 | `test_invalid_manual_rejected_without_state_change`: `422`, **порівняння за ідентифікаторами й полями**, а не лише за кількістю | `tests/test_routes.py` | AC3 | [ ] |
| T031 | `test_ai_creates_record_from_text`: `201`, очікувані змістові поля, рівно один новий запис, збіг зі списком | `tests/test_routes.py` | AC4 | [ ] |
| T032 | `test_ai_incomplete_text_asks_for_clarification`: `422`, `status`, `missing`; жодного нового запису | `tests/test_routes.py` | AC5 | [ ] |
| T033 | `test_ai_structurally_wrong_proposal_rejected`: `422`, `status = rejected`, `reason = invalid_structure`; сховище не змінюється | `tests/test_routes.py` | AC6 | [ ] |
| T034 | `test_ai_semantically_wrong_proposal_rejected`: `422`, `status = rejected`, `reason = invalid_semantics`; сховище не змінюється | `tests/test_routes.py` | AC7 | [ ] |
| T035 | **Тест чутливості**: підмінити очікування на хибне значення і переконатися, що перевірка справді спрацьовує | `tests/test_routes.py` | AC7 | [ ] |
| T036 | `test_model_failure_keeps_manual_path_working`: `503` + `model_unavailable`, сховище не змінюється, `POST /routes` і `GET /routes` працюють і підтверджують новий ручний запис | `tests/test_routes.py` | AC8 | [ ] |

## Блок 8. Підготовлені відповіді та документація (T037–T039)

| ID | Задача | Файл | AC | Статус |
|---|---|---|---|---|
| T037 | `stubs/responses.json`: підготовлені відповіді для `stub`-режиму — коректна, структурно хибна, змістовно хибна, неповна | `stubs/responses.json` | AC4–AC7 | [ ] |
| T038 | README: точні команди встановлення, запуску сервісу, тестів і другого notebook; робоча тека; адреса API; вибір окремого тестового сховища; режими підміни; опис повторного проходу; звіт і навігаційна таблиця «фаза → файл → коміт» | `README.md` | AC10 | [ ] |
| T039 | Перевірка, що `app/` не імпортує `notebooks` і `app.ai` не імпортує `app.storage` | `tests/test_structure.py` | AC9 | [ ] |

## Блок 9. Зовнішня перевірка (T040–T045)

| ID | Задача | Файл | AC | Статус |
|---|---|---|---|---|
| T040 | Другий notebook: HTTP-клієнт на `urllib` (стандартна бібліотека), адреса, таймаут, функція `call_api`, `run_check` | `notebooks/02_api_verification.ipynb` | AC1–AC9 | [ ] |
| T041 | Сценарій «Список і початковий стан»: фіксує початкові записи | `notebooks/02_api_verification.ipynb` | AC2 | [ ] |
| T042 | Сценарії «Ручне створення», «Хибний ручний вхід» — зі звіркою стану **до і після** за ідентифікаторами й полями | `notebooks/02_api_verification.ipynb` | AC1, AC3 | [ ] |
| T043 | Сценарії «Коректна AI-пропозиція», «Неповний або неоднозначний текст», «Структурно хибна пропозиція», «Змістовно хибна пропозиція» | `notebooks/02_api_verification.ipynb` | AC4–AC7 | [ ] |
| T044 | Сценарій «Збій моделі й незалежний ручний шлях» | `notebooks/02_api_verification.ipynb` | AC8 | [ ] |
| T045 | Сценарій «Жива інтеграція через сервіс» + підсумкова таблиця (критерій, сценарій, джерело, очікування, фактичний код, зміни записів, `passed`/`failed`/`not_run`) | `notebooks/02_api_verification.ipynb` | AC9 | [ ] |

---

## Простеження

```text
T001–T004 → T005–T009 → T010–T012 → T013–T017 → T018–T020 → T021–T026 → T027–T036 → T037–T039 → T040–T045
   моделі      правила       сховище        AI            сервіс        HTTP          тести        дані        перевірка
```

Критичний шлях: **T001 → T005 → T013 → T020 → T021 → T028**. Без нього не
працює жодна змістова перевірка.

## Відповідність критеріям

| AC | Задачі | Автотест | Сценарій другого notebook |
|---|---|---|---|
| AC1 | T001, T002, T010, T011, T018, T021, T028 | `test_manual_create_creates_visible_record` | Ручне створення |
| AC2 | T003, T012, T019, T022, T029 | `test_list_returns_items_and_count` | Список і початковий стан |
| AC3 | T001, T021, T030 | `test_invalid_manual_rejected_without_state_change` | Хибний ручний вхід |
| AC4 | T009, T013, T015, T020, T023, T031, T037 | `test_ai_creates_record_from_text` | Коректна AI-пропозиція |
| AC5 | T004, T006, T009, T020, T024, T032, T037 | `test_ai_incomplete_text_asks_for_clarification` | Неповний або неоднозначний текст |
| AC6 | T004, T005, T015, T020, T024, T033, T037 | `test_ai_structurally_wrong_proposal_rejected` | Структурно хибна пропозиція |
| AC7 | T007, T008, T015, T020, T024, T034, T035, T037 | `test_ai_semantically_wrong_proposal_rejected` | Змістовно хибна пропозиція |
| AC8 | T004, T014, T016, T020, T024, T036 | `test_model_failure_keeps_manual_path_working` | Збій моделі й незалежний ручний шлях |
| AC9 | T013, T014, T017, T025, T026, T039 | `test_structure.py` | Жива інтеграція через сервіс |
| AC10 | T038 | — | звірка історії Git |

Жоден критерій не залишається без автоматичної перевірки. AC10 перевіряється
історією Git, а не тестом: очікування лежать у коміті `cc23968`, який передує
коду сервісу.
