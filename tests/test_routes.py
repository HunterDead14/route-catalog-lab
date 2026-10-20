"""Автоматичні тести сервісу.

Кожен тест має прив'язку до критерію приймання зі специфікації
(specs/001-route-catalog/spec.md, §5). Тести перевіряють дві різні речі:

  - збіг із зафіксованими очікуваннями;
  - незмінність стану сховища (за ідентифікаторами й полями, а не лише за
    кількістю) — це те, що потрібно для перевірки відмови.

Жоден тест не вимагає доступу до провайдера: AI-компонент підміняється.
"""

from __future__ import annotations

from tests.conftest import (
    PROPOSAL_INCOMPLETE,
    PROPOSAL_SEMANTIC,
    PROPOSAL_STRUCTURAL,
    PROPOSAL_VALID,
    TEXT_INCOMPLETE,
    TEXT_SEMANTIC,
    TEXT_STRUCTURAL,
    TEXT_VALID,
    FailingProposer,
    FixedProposer,
    snapshot,
    use_proposer,
)

VALID_BODY = {
    "name": "Соколиця",
    "distance_km": 12.5,
    "difficulty": "medium",
    "duration_hours": 4,
}


# ---------------------------------------------------------------- AC1
def test_manual_create_creates_visible_record(client) -> None:
    """AC1: ручне створення повертає 201, а запис видно у наступному списку."""
    before = client.get("/routes").json()
    assert before["count"] == 0
    assert before["items"] == []

    response = client.post("/routes", json=VALID_BODY)
    assert response.status_code == 201, response.text
    created = response.json()

    assert created["name"] == "Соколиця"
    assert created["distance_km"] == 12.5
    assert created["difficulty"] == "medium"
    assert created["duration_hours"] == 4.0
    assert isinstance(created["id"], int)
    assert created["created_at"]

    after = client.get("/routes").json()
    assert after["count"] == len(before["items"]) + 1
    assert created["id"] in [item["id"] for item in after["items"]]
    assert after["items"][-1] == created


# ---------------------------------------------------------------- AC2
def test_list_returns_items_and_count(client) -> None:
    """AC2: список повертає масив items і count, що дорівнює len(items)."""
    empty = client.get("/routes")
    assert empty.status_code == 200
    body = empty.json()
    assert body == {"items": [], "count": 0}
    assert isinstance(body["items"], list)
    assert body["count"] == len(body["items"])

    client.post("/routes", json=VALID_BODY)
    filled = client.get("/routes").json()
    assert filled["count"] == 1
    assert filled["count"] == len(filled["items"])


# ---------------------------------------------------------------- AC3
def test_invalid_manual_rejected_without_state_change(client) -> None:
    """AC3: хибний ручний вхід відхиляється, стан сховища не змінюється."""
    client.post("/routes", json=VALID_BODY)
    before = snapshot(client.get("/routes").json()["items"])

    # distance_km поза діапазоном
    response = client.post(
        "/routes", json={**VALID_BODY, "name": "Хибний", "distance_km": 0.1}
    )
    assert response.status_code == 422, response.text
    assert response.json()["status"] == "rejected"

    # difficulty поза переліком
    response = client.post(
        "/routes", json={**VALID_BODY, "name": "Хибний", "difficulty": "moderate"}
    )
    assert response.status_code == 422, response.text

    # занадто коротка назва
    response = client.post("/routes", json={**VALID_BODY, "name": "Я"})
    assert response.status_code == 422, response.text

    after = snapshot(client.get("/routes").json()["items"])
    assert after == before, "сховище не змінилося"


def test_error_body_has_single_shape(client) -> None:
    """Усі помилки повертаються в одній формі: status, reason, detail."""
    manual = client.post("/routes", json={**VALID_BODY, "distance_km": 0.1})
    assert manual.status_code == 422
    body = manual.json()
    assert set(body) >= {"status", "reason", "detail"}
    assert body["status"] == "rejected"

    use_proposer(client, FixedProposer(response=PROPOSAL_INCOMPLETE))
    ai = client.post("/routes/from-text", json={"text": TEXT_INCOMPLETE})
    assert ai.status_code == 422
    body = ai.json()
    assert set(body) >= {"status", "reason", "detail"}
    assert body["status"] == "needs_clarification"


# ---------------------------------------------------------------- AC4
def test_ai_creates_record_from_text(client) -> None:
    """AC4: коректна пропозиція створює рівно один новий запис."""
    use_proposer(client, FixedProposer(response=PROPOSAL_VALID))
    before = client.get("/routes").json()

    response = client.post("/routes/from-text", json={"text": TEXT_VALID})
    assert response.status_code == 201, response.text
    created = response.json()

    assert created["name"] == "Соколиця"          # службове слово відкинуто
    assert created["distance_km"] == 12.5
    assert created["difficulty"] == "medium"
    assert created["duration_hours"] == 4.0

    after = client.get("/routes").json()
    assert after["count"] == before["count"] + 1
    old_ids = [old["id"] for old in before["items"]]
    new_items = [item for item in after["items"] if item["id"] not in old_ids]
    assert len(new_items) == 1
    assert new_items[0] == created


# ---------------------------------------------------------------- AC5
def test_ai_incomplete_text_asks_for_clarification(client) -> None:
    """AC5: неповний текст -> уточнення, жодного запису не створюється."""
    use_proposer(client, FixedProposer(response=PROPOSAL_INCOMPLETE))
    before = snapshot(client.get("/routes").json()["items"])

    response = client.post("/routes/from-text", json={"text": TEXT_INCOMPLETE})
    assert response.status_code == 422, response.text
    detail = response.json()
    assert detail["status"] == "needs_clarification"
    assert detail["missing"] == ["duration_hours"]
    assert detail["questions"], "клієнт має отримати питання до автора"

    after = snapshot(client.get("/routes").json()["items"])
    assert after == before


# ---------------------------------------------------------------- AC6
def test_ai_structurally_wrong_proposal_rejected(client) -> None:
    """AC6: структурно хибна пропозиція відхиляється, сховище не змінюється."""
    use_proposer(client, FixedProposer(response=PROPOSAL_STRUCTURAL))
    before = snapshot(client.get("/routes").json()["items"])

    response = client.post("/routes/from-text", json={"text": TEXT_STRUCTURAL})
    assert response.status_code == 422, response.text
    detail = response.json()
    assert detail["status"] == "rejected"
    assert "invalid_structure" in detail["reason"]

    after = snapshot(client.get("/routes").json()["items"])
    assert after == before


# ---------------------------------------------------------------- AC7
def test_ai_semantically_wrong_proposal_rejected(client) -> None:
    """AC7: змістовно хибна пропозиція відхиляється, сховище не змінюється."""
    use_proposer(client, FixedProposer(response=PROPOSAL_SEMANTIC))
    before = snapshot(client.get("/routes").json()["items"])

    response = client.post("/routes/from-text", json={"text": TEXT_SEMANTIC})
    assert response.status_code == 422, response.text
    detail = response.json()
    assert detail["status"] == "rejected"
    assert "invalid_semantics" in detail["reason"]
    assert "distance_km" in detail["reason"]

    after = snapshot(client.get("/routes").json()["items"])
    assert after == before


# ---------------------------------------------------------------- AC7 (чутливість)
def test_validation_is_sensitive_to_wrong_value(client) -> None:
    """Чутливість: якщо очікування підмінити на хибне значення, перевірка мусить спрацювати.

    Без цього тесту попередній тест був би «зеленим» і тоді, коли перевірка
    не працювала б взагалі.
    """
    use_proposer(client, FixedProposer(response=PROPOSAL_SEMANTIC))
    response = client.post("/routes/from-text", json={"text": TEXT_SEMANTIC})
    assert response.status_code == 422, "пропозиція з 21 замість 18 мусить відхилятися"

    # Контроль: та сама перевірка, але число тепер збігається з текстом.
    use_proposer(client, FixedProposer(response={**PROPOSAL_SEMANTIC, "distance_km": 18}))
    response = client.post("/routes/from-text", json={"text": TEXT_SEMANTIC})
    assert response.status_code == 201, (
        "з правильним числом запис має створюватися, інакше перевірка надто сувора"
    )


# ---------------------------------------------------------------- AC8
def test_model_failure_keeps_manual_path_working(client) -> None:
    """AC8: збій моделі не змінює сховище, а ручний шлях працює."""
    use_proposer(client, FailingProposer())
    client.post("/routes", json=VALID_BODY)
    before = snapshot(client.get("/routes").json()["items"])

    response = client.post("/routes/from-text", json={"text": TEXT_VALID})
    assert response.status_code == 503, response.text
    detail = response.json()
    assert detail["status"] == "model_unavailable"

    after = snapshot(client.get("/routes").json()["items"])
    assert after == before, "сховище не змінилося"

    # Незалежний ручний шлях досі працює і підтверджує новий запис.
    created = client.post("/routes", json={**VALID_BODY, "name": "Після збою"})
    assert created.status_code == 201
    items = client.get("/routes").json()["items"]
    assert created.json()["id"] in [item["id"] for item in items]
    assert any(item["name"] == "Після збою" for item in items)


# ---------------------------------------------------------------- межі входу
def test_empty_text_rejected_without_calling_model(client) -> None:
    """Порожній текст відхиляється до виклику моделі."""
    proposer = FixedProposer(response=PROPOSAL_VALID)
    use_proposer(client, proposer)

    response = client.post("/routes/from-text", json={"text": "   "})
    assert response.status_code == 422, response.text
    assert proposer.calls == [], "модель не мала викликатися"


def test_too_long_text_rejected_without_calling_model(client) -> None:
    """Надто довгий текст відхиляється до виклику моделі."""
    proposer = FixedProposer(response=PROPOSAL_VALID)
    use_proposer(client, proposer)

    response = client.post("/routes/from-text", json={"text": "х" * 2001})
    assert response.status_code == 422, response.text
    assert proposer.calls == [], "модель не мала викликатися"


def test_unknown_field_rejected(client) -> None:
    """Зайві поля у ручному запиті відхиляються."""
    response = client.post("/routes", json={**VALID_BODY, "id": 99})
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------- AC9
def _imported_modules(path) -> set[str]:
    """Імена модулів, які імпортує файл. Розбір AST, а не пошук слова в тексті."""
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


def test_model_cannot_write_to_storage_directly() -> None:
    """AC9: модуль AI-компонента не імпортує сховище."""
    from pathlib import Path

    import app.ai as ai_module

    imported = _imported_modules(Path(ai_module.__file__))
    assert not any("storage" in name for name in imported), (
        f"AI-компонент імпортує сховище: {sorted(imported)}"
    )


def test_service_does_not_import_notebooks() -> None:
    """AC9: сервіс не імпортує notebook."""
    from pathlib import Path

    import app

    package = Path(app.__file__).parent
    for module in package.glob("*.py"):
        imported = _imported_modules(module)
        assert not any("notebook" in name for name in imported), (
            f"{module.name} імпортує notebook: {sorted(imported)}"
        )
        assert "nbformat" not in imported, f"{module.name} імпортує nbformat"


def test_public_api_has_no_bypass_parameters(client) -> None:
    """AC9: у звичайному API немає параметра, що вмикає підміну або примусовий успіх."""
    import ast
    from pathlib import Path

    import app.main as main_module

    # Режим підміни не читається в HTTP-шарі: перевіряємо реальні виклики
    # os.getenv, а не згадки в docstring.
    tree = ast.parse(Path(main_module.__file__).read_text(encoding="utf-8"))
    env_reads: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", None) or getattr(func, "id", None)
        if name in ("getenv", "environ"):
            if node.args and isinstance(node.args[0], ast.Constant):
                env_reads.add(str(node.args[0].value))
            for keyword in node.keywords:
                if keyword.arg == "default" and isinstance(keyword.value, ast.Constant):
                    env_reads.add(str(keyword.value.value))

    for forbidden in ("ROUTE_LLM_MODE", "ROUTE_LLM_STUB", "live", "stub", "offline"):
        assert forbidden not in env_reads, (
            f"HTTP-шар читає {forbidden}; режим підміни визначається лише в app.ai"
        )

    # У відкритому контракті немає параметрів запиту для перемикання поведінки.
    schema = client.get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            for parameter in operation.get("parameters", []):
                assert "mode" not in parameter["name"].lower(), (
                    f"{method.upper()} {path} має параметр підміни"
                )
                assert parameter["name"] not in ("force", "bypass", "stub"), (
                    f"{method.upper()} {path} має параметр обходу"
                )
