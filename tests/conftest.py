"""Спільні fixtures для тестів сервісу.

Кожен тест працює з окремим тимчасовим сховищем, тому тести не залежать
один від одного й не торкаються робочого data/routes.json.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai import ProposerError  # noqa: E402
from app.main import app  # noqa: E402
from app.storage import RouteStore  # noqa: E402

# Тексти й підготовлені пропозиції, на яких побудовані перевірки.
TEXT_VALID = "Маршрут Соколиця: 12.5 км, середня складність, орієнтовно 4 години."
TEXT_INCOMPLETE = "Маршрут Дубовий Гай, 15 км, складність дуже висока."
TEXT_SEMANTIC = "Маршрут Тиха Гавань, 18 км, середня складність, 5 годин."
TEXT_STRUCTURAL = "Маршрут Кринична Гора: 10 км, легкий, 2 години."

PROPOSAL_VALID = {
    "name": "Маршрут Соколиця",
    "distance_km": 12.5,
    "difficulty": "medium",
    "duration_hours": 4,
}
PROPOSAL_INCOMPLETE = {
    "name": "Дубовий Гай",
    "distance_km": 15,
    "difficulty": "hard",
    "duration_hours": None,
}
# Правильні типи, але число суперечить тексту (18 у тексті, 21 у пропозиції).
PROPOSAL_SEMANTIC = {
    "name": "Тиха Гавань",
    "distance_km": 21,
    "difficulty": "medium",
    "duration_hours": 5,
}
# distance_km не число — структурна помилка.
PROPOSAL_STRUCTURAL = {
    "name": "Кринична Гора",
    "distance_km": "десять",
    "difficulty": "easy",
    "duration_hours": 2,
}


class FixedProposer:
    """Підміна AI-компонента: повертає заготовлену пропозицію або імітує збій."""

    def __init__(self, response=None, error: str | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[str] = []

    def propose(self, text: str) -> dict | None:
        self.calls.append(text)
        if self.error is not None:
            raise ProposerError(self.error, "імітований збій")
        return self.response


class FailingProposer:
    """Провайдер недоступний: повторні спроби не допомагають."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def propose(self, text: str) -> dict | None:
        self.calls.append(text)
        raise ProposerError("provider_unavailable", "модель недоступна")


@pytest.fixture
def store(tmp_path: Path) -> RouteStore:
    return RouteStore(tmp_path / "routes.json")


@pytest.fixture
def client(store: RouteStore) -> TestClient:
    """Клієнт із тестовим сховищем. Провайдера підміняють окремі тести."""
    app.dependency_overrides[get_store_dependency()] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def get_store_dependency():
    from app.main import get_store

    return get_store


def use_proposer(client: TestClient, proposer) -> None:
    """Підміняє AI-компонент для конкретного клієнта."""
    from app.main import get_proposer

    app.dependency_overrides[get_proposer] = lambda: proposer


def snapshot(items: list[dict]) -> list[tuple]:
    """Знімок стану сховища: ідентифікатори й поля, а не лише кількість.

    Для перевірки відмови цього недостатньо: кількість може не змінитися,
    поки запис було перезаписано.
    """
    return tuple(
        (
            item["id"],
            item["name"],
            item["distance_km"],
            item["difficulty"],
            item["duration_hours"],
        )
        for item in items
    )
