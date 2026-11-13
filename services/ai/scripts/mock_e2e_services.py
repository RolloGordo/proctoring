#!/usr/bin/env python3
"""Internal-only fake API and object storage for docker-compose end-to-end tests."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

LOCK = threading.Lock()
STATE_PATH = Path(os.getenv("MOCK_RESULT_PATH", "/state/results.json"))


def read_state(default: dict[str, Any]) -> dict[str, Any]:
    if not STATE_PATH.exists():
        return default
    value = json.loads(STATE_PATH.read_text())
    if not isinstance(value, dict):
        raise ValueError("mock state must be a JSON object")
    return value


def handler_for(role: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, value: object) -> None:
            payload = json.dumps(value).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            route = urlsplit(self.path).path
            if route == "/health":
                self._json(200, {"ok": True, "role": role})
                return
            if role == "api" and route == "/stats":
                with LOCK:
                    state = read_state({"results": [], "retries": 0})
                self._json(
                    200, {"result_count": len(state["results"]), "retry_count": state["retries"]}
                )
                return
            if role == "api" and route.startswith("/api/v1/internal/audio-jobs/"):
                event_id = route.rsplit("/", 1)[-1]
                with LOCK:
                    state = read_state(
                        {"results": [], "retries": 0, "failed_once": [], "started": {}}
                    )
                    state.setdefault("started", {}).setdefault(event_id, time.time())
                    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                    STATE_PATH.write_text(json.dumps(state))
                filename = os.getenv("MOCK_AUDIO_FILE", "P02_A1_base.mp3")
                self._json(
                    200,
                    {
                        "event_id": event_id,
                        "audio_url": f"http://storage-sim:8001/audio/{filename}",
                        "question_statement": (
                            "¿Cuál es la diferencia entre una variable local y una global?"
                        ),
                        "similarity_threshold": 0.6,
                        "synthetic_threshold": 0.5,
                    },
                )
                return
            if role == "storage":
                filename = unquote(route.removeprefix("/audio/"))
                if Path(filename).name != filename:
                    self._json(400, {"error": "invalid path"})
                    return
                audio_path = Path("/audio") / filename
                if not audio_path.is_file():
                    self._json(404, {"error": "audio missing"})
                    return
                content = audio_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            route = urlsplit(self.path).path
            if role != "api" or not route.endswith("/result"):
                self._json(404, {"error": "not found"})
                return
            event_id = route.split("/")[-2]
            content = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid json"})
                return
            with LOCK:
                state = read_state({"results": [], "retries": 0, "failed_once": []})
                if (
                    os.getenv("MOCK_FAIL_FIRST_POST", "false").lower() == "true"
                    and not state["failed_once"]
                ):
                    state["failed_once"].append(event_id)
                    state["retries"] += 1
                    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                    STATE_PATH.write_text(json.dumps(state))
                    self._json(503, {"error": "one simulated transient response"})
                    return
                if not any(row["event_id"] == event_id for row in state["results"]):
                    state["results"].append(
                        {
                            "event_id": event_id,
                            "payload": result,
                            "api_fetch_to_post_seconds": time.time()
                            - state.get("started", {}).get(event_id, time.time()),
                        }
                    )
                STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                STATE_PATH.write_text(json.dumps(state))
            self._json(200, {"alerted": False, "accepted": True})

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("api", "storage"), required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), handler_for(args.role))
    server.serve_forever()


if __name__ == "__main__":
    main()
