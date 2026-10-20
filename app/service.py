"""Сервісний шар: три функції каталогу.

Розділення відповідальності:
  - ручне створення та список не залежать від моделі;
  - створення з тексту: модель пропонує, app.policy перевіряє, сховище
    приймає лише те, що пройшло перевірку.
"""

from __future__ import annotations

from .ai import Proposer, ProposerError, propose_with_retry
from .models import Outcome, Route, RouteCreate
from .policy import validate_proposal
from .storage import RouteStore

MAX_TEXT_LENGTH = 2000
# Стани, за яких повторна спроба не має сенсу: провайдер недоступний —
# це визначений результат, а не тимчасова помилка.
NON_RETRYABLE = ("provider_unavailable", "refused")


def check_text(text: str) -> str:
    """Межа входу: 1..2000 символів, не з самих пробілів.

    Інакше модель не викликається.
    """
    cleaned = text.strip()
    if not cleaned or len(cleaned) > MAX_TEXT_LENGTH:
        raise ValueError(f"Текст має містити від 1 до {MAX_TEXT_LENGTH} символів")
    return cleaned


def create_route(data: RouteCreate, store: RouteStore) -> Route:
    """(1) Ручне створення запису. Не залежить від моделі."""
    return store.add(data)


def list_routes(store: RouteStore) -> list[Route]:
    """(2) Перегляд списку записів. Не залежить від моделі."""
    return store.list()


def create_route_from_text(text: str, proposer: Proposer, store: RouteStore) -> Outcome:
    """(3) Створення запису з тексту.

    Модель пропонує поля, програма перевіряє пропозицію і лише тоді записує.
    Будь-яка відмова, помилка структури, змістове порушення або недоступність
    моделі не змінюють сховище.
    """
    cleaned = check_text(text)

    try:
        proposal = propose_with_retry(proposer, cleaned)
    except ProposerError as error:
        if error.state in NON_RETRYABLE:
            return Outcome(status="model_unavailable", reason=f"{error.state}: {error.detail}")
        # Помилка структури або збій після retry: модель відповіла, але
        # відповідь непридатна — це відхилення пропозиції, а не відсутність моделі.
        return Outcome(status="rejected", reason=f"{error.state}: {error.detail}")

    outcome = validate_proposal(proposal, cleaned)
    if outcome.status == "complete" and outcome.record is not None:
        outcome.record = create_route(outcome.record, store)
    return outcome
