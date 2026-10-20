"""HTTP-ендпоінти каталогу туристичних маршрутів.

Три функції:
  POST /routes           — створити запис вручну (без моделі);
  GET  /routes           — переглянути список (без моделі);
  POST /routes/from-text — створити запис з короткого тексту (модель пропонує,
                           програма перевіряє і вирішує).

У публічному API немає параметрів обходу: режим підміни відповіді моделі
визначається процесом сервісу (ROUTE_LLM_MODE).

Усі помилки мають одну форму: {"status": ..., "reason": ..., "detail": ...}.
HTTP-код і змістовий статус — різні перевірки, тому змістовий статус є
явним полем у тілі, а не лише кодом.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .ai import get_proposer
from .models import Route, RouteCreate, RouteList
from .service import check_text, create_route, create_route_from_text, list_routes
from .storage import RouteStore, db_path

# Налаштування цього проєкту; пріоритет середовища зберігається.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

app = FastAPI(title="Каталог туристичних маршрутів вихідного дня")


def get_store() -> RouteStore:
    """Залежність FastAPI. Тести підміняють її сховищем у тимчасовій теці."""
    return RouteStore(db_path())


class RouteFromText(BaseModel):
    """Тіло запиту для створення запису з тексту."""

    text: str


def error_body(status: str, reason: str, detail: str, **extra) -> dict:
    """Єдина форма тіла помилки для всіх ендпоінтів."""
    return {"status": status, "reason": reason, "detail": detail, **extra}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, error: RequestValidationError) -> JSONResponse:
    """Помилка входу у власну форму помилки, а не в список Pydantic.

    Клієнт має отримувати однакову форму помилки на всіх ендпоінтах,
    щоб розрізняти відмови за полем status, а не за формою тіла.
    """
    problems = error.errors()
    first = problems[0] if problems else {}
    location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    message = first.get("msg", "неправильні дані")
    return JSONResponse(
        status_code=422,
        content=error_body(
            status="rejected",
            reason=f"invalid_input: {location or 'body'}",
            detail=message,
        ),
    )


@app.post("/routes", response_model=Route, status_code=201)
def post_route(data: RouteCreate, store: RouteStore = Depends(get_store)) -> Route:
    """(1) Ручне створення запису. Не залежить від моделі."""
    return create_route(data, store)


@app.get("/routes", response_model=RouteList)
def get_routes(store: RouteStore = Depends(get_store)) -> RouteList:
    """(2) Перегляд списку записів. Не залежить від моделі."""
    items = list_routes(store)
    return RouteList(items=items, count=len(items))


@app.post("/routes/from-text", status_code=201)
def post_route_from_text(
    payload: RouteFromText,
    store: RouteStore = Depends(get_store),
    proposer=Depends(get_proposer),
):
    """(3) Створення запису з тексту.

    Код відповіді і змістовий статус — різні речі: 201 доводить лише те, що
    запис створено, а не те, що його поля правильні. Тому в разі відмови
    тіло містить явний status.
    """
    try:
        cleaned = check_text(payload.text)
    except ValueError as error:
        return JSONResponse(
            status_code=422,
            content=error_body(
                status="rejected",
                reason="invalid_input: text",
                detail=str(error),
            ),
        )

    outcome = create_route_from_text(cleaned, proposer, store)

    if outcome.status == "complete" and outcome.record is not None:
        return outcome.record

    if outcome.status == "needs_clarification":
        return JSONResponse(
            status_code=422,
            content=error_body(
                status="needs_clarification",
                reason=outcome.reason or "incomplete",
                detail="Недостатньо даних для створення запису",
                missing=outcome.missing,
                questions=outcome.questions,
            ),
        )

    if outcome.status == "model_unavailable":
        return JSONResponse(
            status_code=503,
            content=error_body(
                status="model_unavailable",
                reason=outcome.reason or "provider_unavailable",
                detail="Модель недоступна, ручний шлях продовжує працювати",
            ),
        )

    return JSONResponse(
        status_code=422,
        content=error_body(
            status="rejected",
            reason=outcome.reason or "invalid_semantics",
            detail="Пропозицію моделі відхилено",
        ),
    )
