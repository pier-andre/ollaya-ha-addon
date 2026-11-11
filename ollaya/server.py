#!/usr/bin/env python3
"""Home Assistant ingress model manager and protected inference proxy for Ollaya.

Standard-library only. The upstream daemon binds loopback; only inference and
read-only model APIs are made available to other Home Assistant apps.
"""
from collections import deque
from http.cookies import SimpleCookie
import hmac
import html
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

DATA = Path(os.environ.get("OLLAYA_HA_DATA", "/data/ollaya"))
OPTIONS = Path(os.environ.get("OLLAYA_HA_OPTIONS", "/data/options.json"))
DAEMON_HOST = os.environ.get("OLLAYA_HA_DAEMON_HOST", "127.0.0.1")
DAEMON_PORT = int(os.environ.get("OLLAYA_HA_DAEMON_PORT", "11436"))
API_PORT = int(os.environ.get("OLLAYA_HA_API_PORT", "11435"))
UI_PORT = int(os.environ.get("OLLAYA_HA_UI_PORT", "8099"))
INGRESS_IP = os.environ.get("OLLAYA_HA_INGRESS_IP", "172.30.32.2")
MAX_BODY = 8 * 1024 * 1024
MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")

# This packaging is CPU-only and there is no option to change it. Home Assistant
# OS ships no NVIDIA driver and the Supervisor cannot request a GPU runtime, so
# the device is fixed here instead of being offered as a setting. Before
# changing this, read docs/gpu/README.md in the repository.
DEVICE = "cpu"

DEFAULTS = {
    "default_model": "laya:en",
    "model_downloads_enabled": False,
    "keep_alive": "5m",
    "max_loaded_models": 1,
    "threads": 2,
    "max_queue": 16,
    "api_key": "",
}
SUGGESTED = (
    ("laya:en", "model_laya_en"),
    ("laya:typed-decisions", "model_laya_typed"),
    ("laya:multilingual", "model_laya_multi"),
    ("laya", "model_laya_router"),
    ("decima:small", "model_decima"),
    ("nli:modernbert-large", "model_nli"),
)

# Local-only translation catalogs are bundled in the app image.
I18N_DIR = Path(__file__).with_name("i18n")
CATALOG = {lang: json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))
           for lang in ("en", "fr")}
assert CATALOG["en"].keys() == CATALOG["fr"].keys(), "Incomplete language catalog"


def tr(lang, key, **kwargs):
    return CATALOG[lang].get(key, CATALOG["en"].get(key, key)).format(**kwargs)


def select_language(path, headers):
    """Prefer an explicit language, then a saved choice, then browser preferences.

    The preference cookie contains only a whitelisted language code. It is not
    an auth token; ingress remains responsible for admin authentication.
    """
    requested = (parse_qs(urlsplit(path).query).get("lang") or [""])[0]
    if requested in CATALOG:
        return requested, True
    try:
        cookie = SimpleCookie()
        cookie.load(headers.get("Cookie", ""))
        saved = cookie["ollaya_ha_lang"].value if "ollaya_ha_lang" in cookie else None
        if saved in CATALOG:
            return saved, False
    except Exception:
        pass
    preferences = []
    for item in headers.get("Accept-Language", "").split(","):
        parts = item.strip().split(";")
        language = parts[0].lower().split("-", 1)[0]
        try:
            quality = float(parts[1].split("=", 1)[1]) if len(parts) > 1 and parts[1].strip().startswith("q=") else 1.0
        except ValueError:
            quality = 0
        if language in CATALOG and quality > 0:
            preferences.append((quality, language))
    if preferences:
        return sorted(preferences, key=lambda v: -v[0])[0][1], False
    return "en", False


def display_pull_status(status, lang):
    return tr(lang, {
        "No download running": "no_download",
        "Starting model pull": "pull_start",
        "Download completed successfully": "pull_success",
        "Download failed": "pull_failure",
    }.get(status, "")) if status in (
        "No download running", "Starting model pull", "Download completed successfully", "Download failed"
    ) else status



def read_options():
    try:
        value = json.loads(OPTIONS.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("options must be an object")
        return {**DEFAULTS, **value}
    except FileNotFoundError:
        print("[ollaya-ha] WARNING: missing options.json; using defaults", flush=True)
        return DEFAULTS.copy()


def configured_model():
    name = str(CONFIG.get("default_model") or "laya:en").strip()
    return name if MODEL_NAME.fullmatch(name) else "laya:en"


def selected_model():
    try:
        name = (DATA / "selected_model.txt").read_text(encoding="utf-8").strip()
        if MODEL_NAME.fullmatch(name):
            return name
    except FileNotFoundError:
        pass
    return configured_model()


def get_key():
    from_options = str(CONFIG.get("api_key") or "").strip()
    if from_options:
        if len(from_options) < 16:
            raise RuntimeError("api_key must be at least 16 characters")
        return from_options
    file = DATA / "api_key"
    if file.exists():
        value = file.read_text(encoding="utf-8").strip()
        if len(value) >= 32:
            return value
    value = secrets.token_urlsafe(36)
    file.write_text(value + "\n", encoding="utf-8")
    file.chmod(0o600)
    return value


def daemon_connection(timeout=8):
    """Talk to Ollaya via a direct TCP loopback connection, never HTTP_PROXY.

    Ollaya's own outbound registry/Hugging Face traffic is unaffected.
    """
    return http.client.HTTPConnection(DAEMON_HOST, DAEMON_PORT, timeout=timeout)


def daemon_json(method, path, payload=None, timeout=8):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    conn = daemon_connection(timeout=timeout)
    try:
        conn.request(method, path, body=body, headers={"Content-Type": "application/json"})
        reply = conn.getresponse()
        raw = reply.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise ValueError("upstream reply too large")
        if not 200 <= reply.status < 300:
            raise parse_daemon_error(reply.status, raw)
        return json.loads(raw.decode("utf-8")) if raw else {}
    finally:
        conn.close()


class OllayaError(RuntimeError):
    """Upstream API failure with its HTTP status, error code and explanation."""


def parse_daemon_error(status, data):
    code = "UNKNOWN"
    message = "The local Ollaya runtime returned an error without details"
    try:
        value = json.loads(data.decode("utf-8"))
        if isinstance(value, dict):
            code = str(value.get("code") or code)[:80]
            message = str(value.get("error") or message)[:1000]
    except (ValueError, UnicodeDecodeError):
        # Sometimes intermediate proxies return a plain-text/HTML error.
        # Do not echo HTML into the ingress page or system logs.
        pass
    return OllayaError(f"Ollaya HTTP {status} ({code}): {message}")


CONFIG = read_options()
CSRF = secrets.token_urlsafe(32)
PULL_LOCK = threading.Lock()
PULL = {"busy": False, "status": "No download running", "error": "", "name": "", "fraction": ""}
# In-memory operational metrics only. No request bodies, message subjects,
# authorization headers, or email content are stored or logged.
METRICS_LOCK = threading.Lock()
METRICS = {"requests": 0, "successes": 0, "upstream_errors": 0,
           "upstream_timeouts": 0, "client_disconnects": 0, "total_ms": 0}
RECENT = deque(maxlen=25)
STARTED_AT = time.time()
INFERENCE_PATHS = frozenset(("/api/decide", "/v1/systemone", "/v1/decisions"))


def record_request(path, model, status, started, outcome="success"):
    """Record bounded metadata, never the payload or secret-bearing headers."""
    duration = round((time.monotonic() - started) * 1000)
    # The model identifier is metadata, but still validate to avoid log injection.
    safe_model = model if isinstance(model, str) and MODEL_NAME.fullmatch(model) else "(unavailable)"
    with METRICS_LOCK:
        METRICS["requests"] += 1
        METRICS["total_ms"] += duration
        if outcome == "success" and 200 <= status < 400:
            METRICS["successes"] += 1
        elif outcome == "client_disconnected":
            METRICS["client_disconnects"] += 1
        elif outcome == "upstream_timeout":
            METRICS["upstream_timeouts"] += 1
        else:
            METRICS["upstream_errors"] += 1
        RECENT.appendleft({"when": time.strftime("%H:%M:%S UTC", time.gmtime()),
                           "route": path, "model": safe_model,
                           "status": status, "ms": duration, "outcome": outcome})
    # A client disappearing must not generate a traceback or misleading 503.
    if outcome == "client_disconnected":
        print(f"[ollaya-ha] Client disconnected during {path} response after {duration}ms", flush=True)
    elif outcome in ("upstream_timeout", "upstream_unavailable"):
        print(f"[ollaya-ha] {path} {outcome} after {duration}ms", flush=True)


def metrics_snapshot():
    with METRICS_LOCK:
        return METRICS.copy(), list(RECENT)


def runtime_probe():
    """Check Ollaya responsiveness and report the actual upstream version."""
    try:
        result = daemon_json("GET", "/api/version", timeout=3)
        version = result.get("version", "unknown") if isinstance(result, dict) else "unknown"
        return True, str(version)[:80]
    except (OSError, TimeoutError, http.client.HTTPException, ValueError, OllayaError):
        return False, "unavailable"


def runtime_health():
    return runtime_probe()[0]
ALLOWED_API = {
    "GET": {"/", "/health", "/api/version", "/api/tags", "/api/ps", "/v1/models"},
    "HEAD": {"/"},
    "POST": {"/api/decide", "/api/show", "/v1/systemone", "/v1/decisions"},
}


class Handler(BaseHTTPRequestHandler):
    server_version = "OllayaHA/0.1.7"
    sys_version = ""
    mode = "api"

    def log_message(self, fmt, *args):
        # Suppress path/query content and all request bodies from logs.
        pass

    def response(self, code, body=b"", content_type="application/json", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        if content_type.startswith("text/html"):
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'self'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json_error(self, code, reason):
        self.response(code, json.dumps({"error": reason}).encode("utf-8"))

    def read_body(self, limit=MAX_BODY):
        """Read a bounded POST body with either length or HTTP/1.1 chunk framing.

        Ingress can replace the browser's Content-Length with chunked encoding.
        Reject ambiguous framing and enforce limits before allocating memory.
        """
        length = self.headers.get("Content-Length")
        transfer = self.headers.get("Transfer-Encoding", "").strip().lower()
        if transfer:
            if length is not None:
                raise ValueError("conflicting request body framing")
            if transfer != "chunked":
                raise ValueError("unsupported transfer encoding")
            result = bytearray()
            while True:
                header = self.rfile.readline(128)
                if not header or len(header) >= 128 or not header.endswith(b"\r\n"):
                    raise ValueError("malformed chunk size")
                raw_size = header[:-2].split(b";", 1)[0].strip()
                if not raw_size or len(raw_size) > 16 or any(c not in b"0123456789abcdefABCDEF" for c in raw_size):
                    raise ValueError("malformed chunk size")
                size = int(raw_size, 16)
                if size > limit - len(result):
                    raise ValueError("invalid request size")
                if size == 0:
                    # Reject unusually large trailers. The UI forms do not use any.
                    trailer_size = 0
                    while True:
                        trailer = self.rfile.readline(1024)
                        trailer_size += len(trailer)
                        if not trailer or trailer_size > 4096 or not trailer.endswith(b"\r\n"):
                            raise ValueError("malformed chunk trailer")
                        if trailer == b"\r\n":
                            return bytes(result)
                data = self.rfile.read(size + 2)
                if len(data) != size + 2 or not data.endswith(b"\r\n"):
                    raise ValueError("malformed chunk body")
                result.extend(data[:-2])
        if length is None:
            raise ValueError("Content-Length required")
        try:
            count = int(length)
        except ValueError:
            raise ValueError("invalid Content-Length") from None
        if count < 0 or count > limit:
            raise ValueError("invalid request size")
        body = self.rfile.read(count)
        if len(body) != count:
            raise ValueError("incomplete request body")
        return body

    def do_HEAD(self):
        if self.mode == "api" and urlsplit(self.path).path == "/":
            self.response(200, b"", "text/plain; charset=utf-8")
        else:
            self.json_error(404, "not found")

    def do_GET(self):
        if self.mode == "admin":
            self.admin_get()
        else:
            self.proxy_request()

    def do_POST(self):
        if self.mode == "admin":
            self.admin_post()
        else:
            self.proxy_request()

    def do_DELETE(self):
        self.json_error(405, "method not allowed")

    def do_OPTIONS(self):
        self.json_error(405, "method not allowed")

    def proxy_request(self):
        path = urlsplit(self.path).path
        if path not in ALLOWED_API.get(self.command, set()):
            self.json_error(404, "endpoint not exposed")
            return
        if path != "/":
            header = self.headers.get("Authorization", "")
            expected = f"Bearer {API_KEY}"
            if not hmac.compare_digest(header, expected):
                self.json_error(401, "authorization required")
                return
        if path == "/health":
            ready = runtime_health()
            self.response(200 if ready else 503,
                          json.dumps({"status": "ready" if ready else "unavailable",
                                      "runtime": "ollaya", "uptime_seconds": int(time.time() - STARTED_AT)}))
            return
        # The inference-only telemetry deliberately excludes request bodies.
        measured = path in INFERENCE_PATHS
        started = time.monotonic()
        model = "(unavailable)"
        response_status = 0
        conn = None
        try:
            body = self.read_body() if self.command == "POST" else None
            if measured:
                doc = json.loads((body or b"{}").decode("utf-8"))
                if not isinstance(doc, dict):
                    raise ValueError("JSON object required")
                if not doc.get("model"):
                    doc["model"] = selected_model()
                model = doc.get("model")
                body = json.dumps(doc).encode("utf-8")
            conn = daemon_connection(timeout=300)
            conn.request(self.command, path, body=body,
                         headers={"Content-Type": "application/json"})
            reply = conn.getresponse()
            data = reply.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                response_status = 502
                self.json_error(502, "upstream response exceeds limit")
            else:
                response_status = reply.status
                content_type = reply.getheader("Content-Type", "application/json")
                self.response(reply.status, data, content_type)
            if measured:
                record_request(path, model, response_status, started,
                               "success" if 200 <= response_status < 400 else "upstream_error")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # The upstream may have completed normally. Never attempt another
            # HTTP response once the client socket has closed.
            self.close_connection = True
            if measured:
                record_request(path, model, response_status, started, "client_disconnected")
        except (ValueError, UnicodeDecodeError) as exc:
            if measured:
                record_request(path, model, 400, started, "bad_request")
            try:
                self.json_error(400, str(exc))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.close_connection = True
        except (TimeoutError,):
            if measured:
                record_request(path, model, 504, started, "upstream_timeout")
            try:
                self.json_error(504, "local Ollaya runtime timed out")
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.close_connection = True
        except (OSError, http.client.HTTPException):
            if measured:
                record_request(path, model, 503, started, "upstream_unavailable")
            try:
                self.json_error(503, "local Ollaya runtime unavailable")
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                self.close_connection = True
        finally:
            if conn is not None:
                conn.close()

    def ingress_allowed(self):
        # Use the TCP peer address, never X-Forwarded-For.
        return self.client_address[0] == INGRESS_IP

    def admin_get(self):
        if not self.ingress_allowed():
            self.json_error(403, "ingress only")
            return
        if urlsplit(self.path).path not in ("/", ""):
            self.json_error(404, "not found")
            return
        lang, explicit = select_language(self.path, self.headers)
        # The cookie is a UI preference only; model-management permissions are
        # still enforced server-side by Home Assistant ingress and CSRF checks.
        extras = {"Set-Cookie": f"ollaya_ha_lang={lang}; Path=/; Max-Age=31536000; SameSite=Lax; HttpOnly"} if explicit else None
        self.response(200, render_admin(lang), "text/html; charset=utf-8", extra=extras)

    def admin_post(self):
        if not self.ingress_allowed():
            self.json_error(403, "ingress only")
            return
        path = urlsplit(self.path).path
        if path not in ("/pull", "/remove", "/select", "/reset"):
            self.json_error(404, "not found")
            return
        lang, _ = select_language(self.path, self.headers)
        try:
            args = parse_qs(self.read_body(2048).decode("utf-8"), keep_blank_values=True)
            requested_lang = (args.get("lang") or [""])[0]
            if requested_lang in CATALOG:
                lang = requested_lang
            if not hmac.compare_digest((args.get("csrf") or [""])[0], CSRF):
                self.json_error(403, tr(lang, "invalid_form"))
                return
            # Backwards-compatible stored option name; now gates BOTH mutations.
            if path in ("/pull", "/remove") and not CONFIG.get("model_downloads_enabled"):
                raise ValueError(tr(lang, "management_required"))
            model = (args.get("model") or [""])[0].strip()
            if path != "/reset" and not MODEL_NAME.fullmatch(model):
                raise ValueError(tr(lang, "invalid_model"))
            if path == "/pull":
                with PULL_LOCK:
                    if PULL["busy"]:
                        raise ValueError(tr(lang, "another_pull"))
                    PULL.update(busy=True, name=model, status="Starting model pull", error="", fraction="")
                threading.Thread(target=pull_worker, args=(model,), daemon=True).start()
            elif path == "/remove":
                if model == selected_model():
                    raise ValueError(tr(lang, "model_active_remove"))
                daemon_json("DELETE", "/api/delete", {"model": model}, timeout=20)
            elif path == "/select":
                installed = {item.get("name") for item in daemon_json("GET", "/api/tags").get("models", [])}
                if model not in installed and model + ":latest" not in installed:
                    raise ValueError(tr(lang, "model_not_installed"))
                file = DATA / "selected_model.txt"
                temp = DATA / "selected_model.txt.tmp"
                temp.write_text(model + "\n", encoding="utf-8")
                temp.replace(file)
            elif path == "/reset":
                (DATA / "selected_model.txt").unlink(missing_ok=True)
            self.send_response(303)
            self.send_header("Location", f"./?lang={lang}")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        except (ValueError, OllayaError, OSError, http.client.HTTPException) as exc:
            msg = str(exc)
            self.response(400, (f'<!doctype html><html lang="{lang}"><meta charset="utf-8">'
                                f'<h3>{esc(tr(lang, "operation_failed"))}</h3>'
                                f'<p>{esc(msg)}</p>'
                                f'<p><a href="./?lang={lang}">{esc(tr(lang, "back"))}</a></p></html>'),
                          "text/html; charset=utf-8")


class APIHandler(Handler):
    mode = "api"


class AdminHandler(Handler):
    mode = "admin"


def pull_worker(model):
    """Stream model-pull progress and preserve Ollaya's actual failures."""
    def status(message, progress=""):
        with PULL_LOCK:
            PULL.update(status=message, fraction=progress)

    try:
        payload = json.dumps({"model": model, "stream": True}).encode("utf-8")
        conn = daemon_connection(timeout=3600)
        try:
            conn.request("POST", "/api/pull", body=payload,
                         headers={"Content-Type": "application/json"})
            reply = conn.getresponse()
            if not 200 <= reply.status < 300:
                # Ollaya's REGISTRY_ERROR and DIGEST_MISMATCH are both HTTP 502;
                # show the JSON 'code' and 'error' instead of just Bad Gateway.
                raise parse_daemon_error(reply.status, reply.read(8192))
            completed = False
            while True:
                raw = reply.readline(16385)
                if not raw:
                    break
                if len(raw) > 16384:
                    raise OllayaError("Ollaya returned an oversized progress event")
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, dict):
                    raise OllayaError("Unexpected model-pull progress response")
                if data.get("error"):
                    code = str(data.get("code") or "UNKNOWN")[:80]
                    raise OllayaError(f"Ollaya pull error ({code}): {str(data['error'])[:1000]}")
                total = data.get("total") or 0
                done = data.get("completed") or 0
                progress = f"{100 * done / total:.0f}%" if total else ""
                status(str(data.get("status") or "Downloading")[:200], progress)
                if data.get("status") == "success":
                    completed = True
                    break
            if not completed:
                raise OllayaError("Model download ended without Ollaya confirming success")
        finally:
            conn.close()
        status("Download completed successfully")
        print(f"[ollaya-ha] Model pull completed: {model}", flush=True)
    except Exception as exc:
        error = str(exc)[:1200]
        with PULL_LOCK:
            PULL.update(error=error, status="Download failed")
        print(f"[ollaya-ha] Model pull failed for {model}: {error}", flush=True)
    finally:
        with PULL_LOCK:
            PULL["busy"] = False


def esc(value):
    return html.escape(str(value), quote=True)


def render_admin(lang="en"):
    if lang not in CATALOG:
        lang = "en"
    def tx(key, **kwargs):
        return esc(tr(lang, key, **kwargs))

    try:
        models = daemon_json("GET", "/api/tags").get("models", [])
        running = daemon_json("GET", "/api/ps").get("models", [])
        status = tx("runtime_connected", count=len(running))
    except Exception:
        models, running = [], []
        status = tx("runtime_unavailable")
    runtime_ready, runtime_version = runtime_probe()
    counts, recent = metrics_snapshot()
    avg_ms = round(counts["total_ms"] / counts["requests"]) if counts["requests"] else 0
    diag_rows = "".join(
        f"<tr><td>{esc(item['when'])}</td><td>{esc(item['route'])}</td>"
        f"<td><code>{esc(item['model'])}</code></td><td>{item['status']}</td>"
        f"<td>{item['ms']} ms</td><td>{tx('outcome_' + item['outcome'])}</td></tr>"
        for item in recent
    ) or f"<tr><td colspan='6'>{tx('no_requests')}</td></tr>"
    current = selected_model()
    override = (DATA / "selected_model.txt").exists()
    enabled = bool(CONFIG.get("model_downloads_enabled"))
    with PULL_LOCK:
        progress = PULL.copy()

    def form(action, model, label):
        return (f'<form method="post" action="{action}" style="display:inline-block;margin-right:.4rem">'
                f'<input type="hidden" name="csrf" value="{esc(CSRF)}">'
                f'<input type="hidden" name="lang" value="{lang}">'
                f'<input type="hidden" name="model" value="{esc(model)}">'
                f'<button type="submit">{tx(label)}</button></form>')

    rows = []
    for m in models:
        name = str(m.get("name", "?"))
        size = int(m.get("size") or 0) / (1024 * 1024)
        controls = form("select", name, "use_default")
        if enabled and name != current and not (name.endswith(":latest") and name[:-7] == current):
            controls += form("remove", name, "remove")
        rows.append(f"<tr><td><code>{esc(name)}</code></td><td>{size:,.0f} MiB</td><td>{controls}</td></tr>")
    if not rows:
        rows = [f"<tr><td colspan='3'>{tx('no_models')}</td></tr>"]

    suggestions = "".join(f'<option value="{esc(model)}">{tx(label)}</option>' for model, label in SUGGESTED)
    pull_control = (
        f'<form method="post" action="pull"><input type="hidden" name="csrf" value="{esc(CSRF)}">'
        f'<input type="hidden" name="lang" value="{lang}">'
        f'<label>{tx("model_to_pull")} <select name="model">{suggestions}</select></label> '
        f'<button type="submit">{tx("pull_selected")}</button></form>'
        f'<p>{tx("registry_model_note")}</p>'
        f'<form method="post" action="pull"><input type="hidden" name="csrf" value="{esc(CSRF)}">'
        f'<input type="hidden" name="lang" value="{lang}">'
        f'<input type="text" name="model" placeholder="{tx("placeholder_model")}" maxlength="160" required> '
        f'<button type="submit">{tx("pull_custom")}</button></form>'
    ) if enabled else f'<p>{tx("management_disabled")}</p>'

    override_control = form("reset", "", "reset_override") if override else ""
    error_text = f'<p class="err">{esc(progress["error"])}</p>' if progress["error"] else ""
    progress_text = f'{esc(display_pull_status(progress["status"], lang))} {esc(progress["fraction"])}'
    running_names = ", ".join(esc(v.get("name", "?")) for v in running) or tx("none")
    language_links = (f'<nav aria-label="{tx("language")}">'
                      f'<a href="?lang=en" lang="en" aria-current="{str(lang == "en").lower()}">English</a> '
                      f' · <a href="?lang=fr" lang="fr" aria-current="{str(lang == "fr").lower()}">Français</a></nav>')
    return f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{tx('title')}</title><style>
body{{font:15px system-ui,sans-serif;max-width:850px;margin:1.5rem auto;padding:0 1rem;line-height:1.5;background:#101820;color:#ebf0f7}}
section{{border:1px solid #425060;border-radius:10px;padding:1rem;margin:1rem 0}}button{{padding:.4rem .6rem;cursor:pointer}}
select,input{{padding:.45rem;margin:.35rem}}td,th{{border-bottom:1px solid #425060;padding:.6rem;text-align:left}}
table{{width:100%;border-collapse:collapse}}code{{color:#b0e4ee}}.err{{color:#ffb2b2}}small{{color:#acbac9}}
a{{color:#b0e4ee}}nav{{text-align:right}}
</style></head><body>{language_links}<h1>{tx('title')}</h1><p>{status}</p>
<section><h2>{tx('default_model')}</h2><p><strong>{esc(current)}</strong> ({tx('ui_override') if override else tx('ha_configuration')})</p>
<p>{tx('configured_default')}: <code>{esc(configured_model())}</code></p>{override_control}
<p><small>{tx('default_inference_note')}</small></p></section>
<section><h2>{tx('model_storage')}</h2><p>{tx('persistent_directory')}: <code>{esc(DATA / 'models')}</code></p>
<p><small>{tx('storage_note')}</small></p></section>
<section><h2>{tx('model_management')}</h2><p>{progress_text}</p>{error_text}
<p><small>{tx('download_diagnostics')}</small></p>{pull_control}</section>
<section><h2>{tx('installed_models')}</h2><table><thead><tr><th>{tx('model')}</th><th>{tx('on_disk')}</th><th>{tx('actions')}</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table><p><small>{tx('loaded_ram')}: {running_names}</small></p></section>
<section><h2>{tx('inference_api')}</h2><p>{tx('private_port')}</p>
<p>{tx('auth_required')}</p>
<details><summary>{tx('show_key')}</summary><p><code>{esc(API_KEY)}</code></p></details>
<p><small>{tx('api_readonly_note')}</small></p></section>
<section><h2>{tx('diagnostics')}</h2>
<p>{tx('ollaya_runtime')}: <strong>{tx('ready') if runtime_ready else tx('unavailable')}</strong>
({tx('version')}: <code>{esc(runtime_version)}</code>).
{tx('uptime')}: {int(time.time() - STARTED_AT)} {tx('seconds')}.</p>
<p><small>{tx('health_note')}</small></p>
<p>{tx('requests')}: <strong>{counts['requests']}</strong> | {tx('success')}: <strong>{counts['successes']}</strong> |
{tx('upstream_errors')}: <strong>{counts['upstream_errors']}</strong> |
{tx('timeouts')}: <strong>{counts['upstream_timeouts']}</strong> |
{tx('disconnects')}: <strong>{counts['client_disconnects']}</strong> |
{tx('avg_elapsed')}: <strong>{avg_ms} ms</strong></p>
<p><small>{tx('memory_metrics_note')}</small></p>
<table><thead><tr><th>{tx('when')}</th><th>{tx('route')}</th><th>{tx('model')}</th><th>{tx('http')}</th><th>{tx('elapsed')}</th><th>{tx('outcome')}</th></tr></thead>
<tbody>{diag_rows}</tbody></table></section>
<p><a href="./?lang={lang}">{tx('refresh')}</a></p></body></html>'''


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    print(f"[ollaya-ha] Persistent model storage: {DATA / 'models'}", flush=True)
    print(
        f"[ollaya-ha] CPU-only edition: Ollaya runs with OLLAYA_DEVICE={DEVICE}; "
        "no GPU acceleration is used or available (see docs/gpu/README.md)",
        flush=True,
    )
    global API_KEY
    API_KEY = get_key()
    env = dict(os.environ)
    env.update({
        "OLLAYA_HOST": f"{DAEMON_HOST}:{DAEMON_PORT}",
        "OLLAYA_MODELS": str(DATA / "models"),
        "OLLAYA_DEVICE": DEVICE,
        "OLLAYA_KEEP_ALIVE": str(CONFIG.get("keep_alive") or "5m"),
        "OLLAYA_MAX_LOADED_MODELS": str(CONFIG.get("max_loaded_models") or 1),
        "OLLAYA_THREADS": str(CONFIG.get("threads") or 2),
        "OLLAYA_MAX_QUEUE": str(CONFIG.get("max_queue") or 16),
    })
    # The Ollaya daemon is loopback-only. All caller-facing auth lives in the
    # protected proxy rather than in the daemon's local communication channel.
    env.pop("OLLAYA_API_KEY", None)
    child = subprocess.Popen(["/usr/bin/ollaya", "serve"], env=env)
    api = ThreadingHTTPServer(("0.0.0.0", API_PORT), APIHandler)
    ui = ThreadingHTTPServer(("0.0.0.0", UI_PORT), AdminHandler)
    threading.Thread(target=api.serve_forever, daemon=True).start()
    threading.Thread(target=ui.serve_forever, daemon=True).start()
    print(
        f"[ollaya-ha] CPU-only runtime and secure proxy started (device={DEVICE}); "
        "API port 11435; ingress port 8099",
        flush=True,
    )
    try:
        while child.poll() is None:
            time.sleep(1)
        raise RuntimeError(f"Ollaya runtime exited unexpectedly with code {child.returncode}")
    finally:
        api.shutdown()
        ui.shutdown()
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()


if __name__ == "__main__":
    main()
