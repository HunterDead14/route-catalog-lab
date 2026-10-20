"""Правила застосунку після моделі.

Модель лише пропонує поля. Цей модуль вирішує, яке значення можна прийняти,
якого бракує (тоді програма питає автора) і яке порушує правила (тоді —
відхилення без збереження).

Порядок перевірок важливий для передбачуваності:
    1. структура   -> rejected(invalid_structure)
    2. повнота     -> needs_clarification(missing)
    3. діапазон    -> rejected(invalid_semantics)
    4. звірка      -> rejected(invalid_semantics)

Жоден крок не виправляє значення на льоту: помилка моделі не «рятується».
"""

from __future__ import annotations

import re

from .models import (
    ALLOWED_DIFFICULTY,
    DISTANCE_MAX,
    DISTANCE_MIN,
    DURATION_MAX,
    DURATION_MIN,
    NAME_MAX,
    NAME_MIN,
    Outcome,
    RouteCreate,
)

# Число в тексті: 12, 12.5, 12,5
_NUMBER = r"\d+(?:[.,]\d+)?"

# Службове слово перед назвою. Відкидається нормалізацією.
# Модель часто пише «Маршрут Соколиця» замість «Соколиця» — в каталозі такий
# запис виглядає неохайно. Рішення D7, обґрунтування — в першому notebook.
_SERVICE_WORD = re.compile(
    r"^(?:маршрут\w*|марафон|маршружок|трейк)\s+",
    re.IGNORECASE,
)

# Питання до автора за відсутніми полями. Порядок відповідає порядку полів.
_QUESTIONS: dict[str, str] = {
    "name": "Як називається маршрут?",
    "distance_km": "Скільки кілометрів становить маршрут?",
    "difficulty": "Яка складність маршруту (easy, medium або hard)?",
    "duration_hours": "Скільки годин триває маршрут?",
}


def normalize_name(raw: str) -> str:
    """Обрізає пробіли та відкидає службове слово перед назвою."""
    name = str(raw).strip().strip('"\'«»').strip()
    name = _SERVICE_WORD.sub("", name).strip()
    return name


def numbers_in(text: str) -> list[float]:
    """Усі числа, згадані в тексті повідомлення."""
    return [float(raw.replace(",", ".")) for raw in re.findall(_NUMBER, text)]


def number_present(value: float, candidates: list[float]) -> bool:
    """Чи є число з пропозиції присутнім у тексті.

    Допускається округлення цілого: якщо в тексті 12.5, пропозиція 12 або 13
    вважається відповіддю тому самому числу. Але 21 замість 18 — ні.
    """
    for candidate in candidates:
        if abs(value - candidate) < 1e-9:
            return True
        if candidate == int(candidate) and abs(value - candidate) < 0.5:
            return True
    return False


def questions_for(missing: list[str]) -> list[str]:
    """Питання до автора за відсутніми полями."""
    return [_QUESTIONS[field] for field in missing if field in _QUESTIONS]


def validate_proposal(proposal: object, source_text: str) -> Outcome:
    """Перевіряє пропозицію моделі. Повертає Outcome.

    Джерело правил: specs/001-route-catalog/spec.md, §3.3.
    """
    if not isinstance(proposal, dict):
        return Outcome(status="rejected", reason="invalid_structure: пропозиція не об'єкт")

    fields = ("name", "distance_km", "difficulty", "duration_hours")
    present = {field: proposal.get(field) for field in fields}

    # 1. Структура: ключі присутні, типи правильні.
    for field in fields:
        if field not in proposal:
            return Outcome(status="rejected", reason=f"invalid_structure: немає поля {field}")
    for field in ("distance_km", "duration_hours"):
        value = present[field]
        if value is not None and isinstance(value, bool):
            return Outcome(status="rejected", reason=f"invalid_structure: {field} не число")
        if value is not None and not isinstance(value, (int, float)):
            return Outcome(status="rejected", reason=f"invalid_structure: {field} не число")
    if present["difficulty"] is not None and not isinstance(present["difficulty"], str):
        return Outcome(status="rejected", reason="invalid_structure: difficulty не рядок")

    # 2. Повнота: null означає «у тексті немає значення» — це уточнення, а не
    #    помилка структури.
    missing = [field for field in fields if present[field] is None]
    if missing:
        return Outcome(
            status="needs_clarification",
            missing=missing,
            questions=questions_for(missing),
            reason="incomplete",
        )

    # 3. Діапазон і перелік.
    name = normalize_name(present["name"])
    if not (NAME_MIN <= len(name) <= NAME_MAX):
        return Outcome(status="rejected", reason="invalid_semantics: довжина name")
    if present["difficulty"] not in ALLOWED_DIFFICULTY:
        return Outcome(status="rejected", reason="invalid_semantics: difficulty не в переліку")
    for field, low, high in (
        ("distance_km", DISTANCE_MIN, DISTANCE_MAX),
        ("duration_hours", DURATION_MIN, DURATION_MAX),
    ):
        value = float(present[field])
        if not (low <= value <= high):
            return Outcome(status="rejected", reason=f"invalid_semantics: {field} поза діапазоном")

    # 4. Звірка числа з текстом: ловить «правильний тип, хибне значення».
    candidates = numbers_in(source_text)
    for field in ("distance_km", "duration_hours"):
        if not number_present(float(present[field]), candidates):
            return Outcome(
                status="rejected",
                reason=f"invalid_semantics: {field} не знайдено в тексті",
            )

    record = RouteCreate(
        name=name,
        distance_km=float(present["distance_km"]),
        difficulty=present["difficulty"],
        duration_hours=float(present["duration_hours"]),
    )
    return Outcome(status="complete", record=record)
