"""Повний прохід зовнішньої перевірки: три режими сервера в одному kernel-сеансі.

Запускається з корня проєкту:

    .venv\\Scripts\\python.exe scripts\\verify_api.py

Що робить:
  1. піднімає сервер у режимі stub і виконує комірки до сценарію збою;
  2. перезапускає сервер у режимі offline і виконує сценарій збою моделі;
  3. перезапускає сервер у режимі live і виконує сценарій живої інтеграції;
  4. виконує підсумкову комірку і зберігає notebook із фактичними результатами.

Ядро notebook лишається тим самим наскрізь, тому CASE_RESULTS накопичується, а
підсумкова таблиця містить усі дев'ять сценаріїв.

Режим live потребує ключа провайдера у .env. Якщо його немає, сценарій живої
інтеграції буде позначений not_run — це відсутній доказ, а не провал.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from jupyter_client import KernelManager

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK = ROOT / "notebooks" / "02_api_verification.ipynb"
PORT = 8000
STUB_FILE = ROOT / "stubs" / "responses.json"

server: subprocess.Popen | None = None
current_mode: str | None = None


def start_server(mode: str) -> None:
    """Піднімає сервер у режимі mode з окремим сховищем."""
    global server, current_mode
    stop_server()

    db = ROOT / "data" / f"test-routes-{mode}.json"
    if db.exists():
        db.unlink()

    env = dict(os.environ)
    env["ROUTE_LLM_MODE"] = mode
    env["ROUTES_DB"] = str(db)
    env["ROUTE_LLM_STUB"] = str(STUB_FILE)

    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/routes", timeout=3).read()
            break
        except urllib.error.HTTPError:
            break
        except Exception:
            time.sleep(0.5)
    else:
        raise SystemExit(f"Сервер у режимі {mode} не піднявся")

    current_mode = mode
    print(f"  сервер піднято в режимі {mode} (сховище {db.name})")


def stop_server() -> None:
    global server
    if server is not None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        server = None


def main() -> int:
    if not NOTEBOOK.exists():
        print(f"Не знайдено notebook: {NOTEBOOK}")
        return 1

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = notebook["cells"]

    manager = KernelManager()
    manager.start_kernel()
    client = manager.client()
    client.start_channels()
    client.wait_for_ready()

    def run_cell(cell: dict) -> None:
        source = cell["source"]
        if isinstance(source, list):
            source = "".join(source)
        msg_id = client.execute(source)
        outputs = []
        while True:
            message = client.get_iopub_msg(timeout=300)
            if message["parent_header"].get("msg_id") != msg_id:
                continue
            kind = message["msg_type"]
            content = message["content"]
            if kind == "stream":
                outputs.append({"output_type": "stream", "name": content["name"], "text": content["text"]})
            elif kind == "error":
                outputs.append({
                    "output_type": "error",
                    "ename": content["ename"],
                    "evalue": content["evalue"],
                    "traceback": content.get("traceback", []),
                })
            elif kind in ("execute_result", "display_data"):
                outputs.append({
                    "output_type": kind,
                    "data": content["data"],
                    "metadata": content.get("metadata", {}),
                })
            elif kind == "execute_input":
                cell["execution_count"] = content["execution_count"]
            elif kind == "status" and content["execution_state"] == "idle":
                break
        cell["outputs"] = outputs

    try:
        for index, cell in enumerate(cells):
            if cell.get("cell_type") != "code":
                continue
            mode = cell.get("metadata", {}).get("server_mode", "stub")
            if mode == "none":
                # Комірці сервер не потрібен (підсумок за накопиченими результатами).
                print(f"  комірка {index} (сервер не потрібен)")
                run_cell(cell)
                continue
            if mode != current_mode:
                start_server(mode)
            print(f"  комірка {index} (режим {mode})")
            run_cell(cell)
    finally:
        stop_server()
        client.stop_channels()
        manager.shutdown_kernel()

    NOTEBOOK.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nNotebook збережено з результатами: {NOTEBOOK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
