from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from continuum.api.service import InvestigationService
from continuum.graph.client import GraphClient, GraphConfig

ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend"


def make_handler(service: InvestigationService):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ContinuumM17/1.0"

        def _send_json(self, status: int, payload: object) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path, content_type: str) -> None:
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            try:
                if path == "/":
                    return self._send_file(
                        FRONTEND / "index.html", "text/html; charset=utf-8"
                    )
                if path == "/app.js":
                    return self._send_file(
                        FRONTEND / "app.js", "text/javascript; charset=utf-8"
                    )
                if path == "/styles.css":
                    return self._send_file(
                        FRONTEND / "styles.css", "text/css; charset=utf-8"
                    )
                if path == "/api/health":
                    return self._send_json(HTTPStatus.OK, service.health())
                if path == "/api/worlds":
                    return self._send_json(HTTPStatus.OK, {"worlds": service.worlds()})
                parts = path.split("/")
                if len(parts) == 4 and parts[1:3] == ["api", "investigations"]:
                    return self._send_json(HTTPStatus.OK, service.get(parts[3]))
                if (
                    len(parts) == 5
                    and parts[1:3] == ["api", "investigations"]
                    and parts[4] == "graph"
                ):
                    return self._send_json(
                        HTTPStatus.OK, service.graph_projection(parts[3])
                    )
                if (
                    len(parts) == 5
                    and parts[1:3] == ["api", "investigations"]
                    and parts[4] == "evidence"
                ):
                    evidence_id = parse_qs(parsed.query).get("id", [""])[0]
                    return self._send_json(
                        HTTPStatus.OK, service.evidence(parts[3], evidence_id)
                    )
                if path.startswith("/api/"):
                    return self._send_json(
                        HTTPStatus.NOT_FOUND, {"error": "route_not_found"}
                    )
                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            except KeyError:
                self._send_json(
                    HTTPStatus.NOT_FOUND, {"error": "investigation_not_found"}
                )
            except (RuntimeError, ValueError) as exc:
                self._send_json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"error": type(exc).__name__, "detail": str(exc)},
                )

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.rstrip("/") != "/api/investigations":
                return self._send_json(
                    HTTPStatus.NOT_FOUND, {"error": "route_not_found"}
                )
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                payload = service.create(
                    question=str(body.get("question", "")),
                    domain=str(body.get("domain", "")),
                    target_id=body.get("target_id"),
                )
                self._send_json(HTTPStatus.CREATED, payload)
            except ValueError as exc:
                detail = str(exc)
                status = (
                    HTTPStatus.NOT_FOUND
                    if "does not match the investigated target" in detail
                    else HTTPStatus.BAD_REQUEST
                )
                code = (
                    "target_not_found"
                    if status == HTTPStatus.NOT_FOUND
                    else "invalid_request"
                )
                self._send_json(status, {"error": code, "detail": detail})
            except (RuntimeError, KeyError) as exc:
                status = HTTPStatus.SERVICE_UNAVAILABLE
                code = "investigation_failed"
                detail = str(exc)
                self._send_json(status, {"error": code, "detail": detail})

        def log_message(self, format: str, *args) -> None:
            print(f"M17 HTTP · {format % args}")

    return Handler


def run_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    graph_host: str = "localhost",
    graph_port: int = 6379,
    graph_name: str = "continuum-m17",
) -> None:
    graph = GraphClient(
        GraphConfig(host=graph_host, port=graph_port, graph_name=graph_name)
    )
    service = InvestigationService(graph)
    server = ThreadingHTTPServer((host, port), make_handler(service))
    print(f"CONTINUUM M17 UI http://{host}:{port}")
    print("API /api/health /api/worlds /api/investigations")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCONTINUUM M17 stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server(
        host=os.getenv("M17_HOST", "127.0.0.1"),
        port=int(os.getenv("M17_PORT", "8000")),
        graph_host=os.getenv("FALKORDB_HOST", "localhost"),
        graph_port=int(os.getenv("FALKORDB_PORT", "6379")),
        graph_name=os.getenv("FALKORDB_GRAPH", "continuum-m17"),
    )
