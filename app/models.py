"""Моделі даних сервісу.

RouteCreate — те, що приходить від клієнта.
Route — те, що сервіс зберігає і віддає.
Outcome — результат перевірки пропозиції моделі: створити запис, запитати
уточнення або відхилити пропозицію.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Межі полів. Джерело: specs/001-route-catalog/spec.md, §2.1.
NAME_MIN = 3
NAME_MAX = 80
DISTANCE_MIN = 0.5
DISTANCE_MAX = 100.0
DURATION_MIN = 0.5
DURATION_MAX = 24.0

Difficulty = Literal["easy", "medium", "hard"]
ALLOWED_DIFFICULTY: tuple[str, ...] = ("easy", "medium", "hard")

# Змістовий статус відповіді. HTTP-код і змістовий статус — різні перевірки,
# тому статус їде в тілі, а не лише в код.
OutcomeStatus = Literal["complete", "needs_clarification", "rejected", "model_unavailable"]


class RouteCreate(BaseModel):
    """Вхід ручного створення. Поля id/created_at клієнт не передає.

    extra="forbid": зайві поля відхиляються (422), а не ігноруються —
    інакше клієнт міг би випадково передати id, а сервер мовчки його
    проігнорував би, створивши запис не з тим ідентифікатором.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=NAME_MIN, max_length=NAME_MAX)
    distance_km: float = Field(ge=DISTANCE_MIN, le=DISTANCE_MAX)
    difficulty: Difficulty
    duration_hours: float = Field(ge=DURATION_MIN, le=DURATION_MAX)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < NAME_MIN:
            raise ValueError(f"назва має містити щонайменше {NAME_MIN} символи")
        return cleaned


class Route(BaseModel):
    """Збережений запис."""

    id: int
    name: str
    distance_km: float
    difficulty: Difficulty
    duration_hours: float
    created_at: str


class RouteList(BaseModel):
    """Відповідь на GET /routes."""

    items: list[Route]
    count: int


class ClarificationError(BaseModel):
    """Відмова: бракує даних. Запис не створюється."""

    status: Literal["needs_clarification"] = "needs_clarification"
    missing: list[str]
    questions: list[str]
    detail: str


class RejectionError(BaseModel):
    """Відмова: пропозиція порушує правила застосунку."""

    status: Literal["rejected"] = "rejected"
    reason: str
    detail: str


class ModelUnavailableError(BaseModel):
    """Відмова: модель недоступна. Ручний шлях продовжує працювати."""

    status: Literal["model_unavailable"] = "model_unavailable"
    reason: str
    detail: str


class Outcome(BaseModel):
    """Результат перевірки пропозиції моделі.

    record заповнений лише при status == complete. Перед перевіркою це
    RouteCreate (перевірені поля), після збереження — Route (із id і
    created_at). Для needs_clarification заповнений missing, для rejected —
    reason.
    """

    status: OutcomeStatus
    record: RouteCreate | Route | None = None
    missing: list[str] = []
    questions: list[str] = []
    reason: str | None = None
