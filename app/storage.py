"""Локальне сховище записів.

JSON-файл, шлях задається змінною ROUTES_DB (типово data/routes.json).
Окремий файл — окреме тестове сховище для зовнішньої перевірки через HTTP.

Модуль навмисно не імпортує app.ai: модель не має доступу до сховища.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .models import Route, RouteCreate

DEFAULT_DB_PATH = "data/routes.json"


def db_path() -> Path:
    """Шлях файлу сховища з налаштування середовища."""
    return Path(os.getenv("ROUTES_DB", DEFAULT_DB_PATH))


class RouteStore:
    """Зберігає записи у JSON-файлі."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else db_path()

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        return json.loads(raw)

    def _write(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Атомарний запис: спершу в тимчасовий файл, потім перейменування.
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def list(self) -> list[Route]:
        """Усі записи у порядку зростання id (порядок визначено специфікацією)."""
        return [Route(**item) for item in sorted(self._read(), key=lambda item: item["id"])]

    def add(self, data: RouteCreate) -> Route:
        """Додає запис і повертає його. Наступний id не перевикористовується."""
        items = self._read()
        next_id = max((item["id"] for item in items), default=0) + 1
        record = Route(
            id=next_id,
            name=data.name,
            distance_km=data.distance_km,
            difficulty=data.difficulty,
            duration_hours=data.duration_hours,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        items.append(record.model_dump())
        self._write(items)
        return record
