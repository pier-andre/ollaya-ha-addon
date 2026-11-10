"""Unit and HTTP smoke tests for the app's public API restrictions.

Run with: python3 -m unittest discover -s tests -v
No Ollaya installation or Docker required; a mock local runtime is used.
"""
import http.client
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from urllib.parse import urlencode
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]


class MockOllaya(BaseHTTPRequestHandler):
    pulls = []
    deletes = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/api/version":
            self.reply({"version": "0.13.0-test"})
        else:
            self.reply({"models": [{"name": "laya:en", "size": 1000}] if self.path == "/api/tags" else []})

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        val = json.loads(body or b"{}")
        if self.path == "/api/decide":
            if val.get("model") == "fail:inference":
                self.reply({"error": "synthetic upstream error"}, status=503)
            else:
                self.reply(val)
        elif self.path == "/api/pull":
            self.pulls.append(val["model"])
            name = val["model"]
            if name == "fail:registry":
                self.reply({"code": "REGISTRY_ERROR", "error": "registry DNS lookup failed"}, status=502)
                return
            if name == "fail:digest":
                raw = b'{"status":"pulling manifest"}\n{"code":"DIGEST_MISMATCH","error":"sha256 verification failed"}\n'
            elif name == "fail:incomplete":
                raw = b'{"status":"pulling manifest"}\n'
            else:
                raw = b'{"status":"success"}\n'
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        else:
            self.reply({})

    def do_DELETE(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.deletes.append(json.loads(body or b"{}").get("model"))
        self.reply({})

    def reply(self, body, status=200):
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class ProxyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        options = Path(cls.temp.name) / "options.json"
        options.write_text(json.dumps({
            "default_model": "laya:en",
            "model_downloads_enabled": False,
        }))
        os.environ["OLLAYA_HA_OPTIONS"] = str(options)
        os.environ["OLLAYA_HA_DATA"] = cls.temp.name
        os.environ["OLLAYA_HA_INGRESS_IP"] = "127.0.0.1"
        cls.fake = ThreadingHTTPServer(("127.0.0.1", 0), MockOllaya)
        os.environ["OLLAYA_HA_DAEMON_PORT"] = str(cls.fake.server_port)
        threading.Thread(target=cls.fake.serve_forever, daemon=True).start()
        spec = importlib.util.spec_from_file_location("ollaya_server", ROOT / "ollaya" / "server.py")
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.mod.API_KEY = cls.mod.get_key()
        cls.api = ThreadingHTTPServer(("127.0.0.1", 0), cls.mod.APIHandler)
        cls.ui = ThreadingHTTPServer(("127.0.0.1", 0), cls.mod.AdminHandler)
        threading.Thread(target=cls.api.serve_forever, daemon=True).start()
        threading.Thread(target=cls.ui.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for server in (cls.api, cls.ui, cls.fake):
            server.shutdown()
            server.server_close()
        cls.temp.cleanup()

    def api_request(self, method, path, data=None, auth=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.api.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = "Bearer " + self.mod.API_KEY
        conn.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers)
        response = conn.getresponse()
        body = response.read()
        code = response.status
        conn.close()
        return code, body

    def admin_request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.ui.server_port, timeout=5)
        conn.request(method, path, body=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        response = conn.getresponse()
        code = response.status
        data = response.read()
        conn.close()
        return code, data

    def test_auth_mandatory(self):
        code, _ = self.api_request("GET", "/api/tags", auth=False)
        self.assertEqual(401, code)

    def test_model_management_not_exposed(self):
        for route in ("/api/pull", "/api/create", "/api/delete", "/api/copy"):
            code, _ = self.api_request("POST", route, {"model": "laya:en"})
            self.assertEqual(404, code, route)

    def test_inference_default_model(self):
        code, raw = self.api_request("POST", "/api/decide", {"state": "hello", "questions": {}})
        self.assertEqual(200, code)
        self.assertEqual("laya:en", json.loads(raw)["model"])

    def test_inference_explicit_model(self):
        code, raw = self.api_request("POST", "/api/decide", {"model": "laya:typed-decisions", "state": "hi", "questions": {}})
        self.assertEqual(200, code)
        self.assertEqual("laya:typed-decisions", json.loads(raw)["model"])

    def test_ingress_dashboard(self):
        code, raw = self.admin_request("GET", "/")
        self.assertEqual(200, code)
        self.assertIn(b"laya:en", raw)
        self.assertIn(b"Model management is disabled", raw)
        self.assertIn(b"Model storage", raw)
        self.assertIn(b"/models", raw)

    def test_ingress_csrf_rejects(self):
        code, _ = self.admin_request("POST", "/select", "model=laya%3Aen&csrf=bogus")
        self.assertEqual(403, code)

    def test_ingress_rejects_downloads_when_disabled(self):
        code, _ = self.admin_request("POST", "/pull", "model=laya%3Aen&csrf=" + self.mod.CSRF)
        self.assertEqual(400, code)

    def admin_chunked_request(self, path, fields):
        body = urlencode(fields).encode("utf-8")
        pieces = (body[i:i + 4096] for i in range(0, len(body), 4096))
        conn = http.client.HTTPConnection("127.0.0.1", self.ui.server_port, timeout=5)
        conn.request(
            "POST", path, body=pieces,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            encode_chunked=True,
        )
        response = conn.getresponse()
        result = response.status, response.read()
        conn.close()
        return result

    def test_chunked_ingress_pull_from_dropdown_and_custom_input(self):
        """Regression: HA ingress streaming may strip Content-Length."""
        previous = self.mod.CONFIG["model_downloads_enabled"]
        self.mod.CONFIG["model_downloads_enabled"] = True
        try:
            for name in ("laya:en", "decima:small"):
                with self.subTest(name=name):
                    code, raw = self.admin_chunked_request(
                        "/pull", {"csrf": self.mod.CSRF, "model": name}
                    )
                    self.assertEqual(303, code, raw.decode("utf-8", errors="replace"))
                    deadline = time.monotonic() + 5
                    while self.mod.PULL["busy"] and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertFalse(self.mod.PULL["busy"])
                    self.assertEqual("", self.mod.PULL["error"])
                    self.assertIn(name, MockOllaya.pulls)
        finally:
            self.mod.CONFIG["model_downloads_enabled"] = previous

    def test_chunked_ingress_csrf_rejected(self):
        code, _ = self.admin_chunked_request("/pull", {"csrf": "wrong", "model": "laya:en"})
        self.assertEqual(403, code)

    def test_chunked_ingress_oversized_body_rejected(self):
        code, raw = self.admin_chunked_request(
            "/pull", {"csrf": self.mod.CSRF, "model": "laya:en", "extra": "x" * 2100}
        )
        self.assertEqual(400, code)
        self.assertIn(b"invalid request size", raw)

    def test_conflicting_http_body_framing_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.ui.server_port, timeout=5)
        body = urlencode({"csrf": self.mod.CSRF, "model": "laya:en"})
        conn.request("POST", "/pull", body=body, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(body)),
            "Transfer-Encoding": "chunked",
        })
        res = conn.getresponse()
        self.assertEqual(400, res.status)
        self.assertIn(b"conflicting request body framing", res.read())
        conn.close()

    def test_registry_error_retains_ollaya_json_code_and_reason(self):
        self.mod.PULL.update(error="", busy=True, status="Starting")
        self.mod.pull_worker("fail:registry")
        self.assertEqual("Download failed", self.mod.PULL["status"])
        self.assertIn("HTTP 502", self.mod.PULL["error"])
        self.assertIn("REGISTRY_ERROR", self.mod.PULL["error"])
        self.assertIn("registry DNS lookup failed", self.mod.PULL["error"])
        self.assertIn(b"REGISTRY_ERROR", self.mod.render_admin().encode())

    def test_streamed_sha256_error_is_preserved(self):
        self.mod.PULL.update(error="", busy=True, status="Starting")
        self.mod.pull_worker("fail:digest")
        self.assertIn("DIGEST_MISMATCH", self.mod.PULL["error"])
        self.assertIn("sha256 verification failed", self.mod.PULL["error"])

    def test_truncated_model_pull_cannot_report_success(self):
        self.mod.PULL.update(error="", busy=True, status="Starting")
        self.mod.pull_worker("fail:incomplete")
        self.assertEqual("Download failed", self.mod.PULL["status"])
        self.assertIn("without Ollaya confirming success", self.mod.PULL["error"])

    def test_loopback_requests_ignore_system_http_proxy(self):
        self.mod.PULL.update(error="", busy=True, status="Starting")
        with patch.dict(os.environ, {
            "HTTP_PROXY": "http://127.0.0.1:1",
            "http_proxy": "http://127.0.0.1:1",
            "NO_PROXY": "",
            "no_proxy": "",
        }):
            self.mod.pull_worker("laya:en")
            self.assertEqual("Download completed successfully", self.mod.PULL["status"])
            data = self.mod.daemon_json("GET", "/api/tags")
            self.assertIn("models", data)

    def test_health_is_authenticated_and_checks_upstream(self):
        code, _ = self.api_request("GET", "/health", auth=False)
        self.assertEqual(401, code)
        code, body = self.api_request("GET", "/health")
        self.assertEqual(200, code)
        self.assertEqual("ready", json.loads(body)["status"])
        with patch.object(self.mod, "DAEMON_PORT", 1):
            code, body = self.api_request("GET", "/health")
            self.assertEqual(503, code)
            self.assertEqual("unavailable", json.loads(body)["status"])

    def test_inference_metrics_are_bounded_and_private(self):
        secret = "CONFIDENTIAL_EMAIL_BODY_token_98765"
        old_count = self.mod.metrics_snapshot()[0]["requests"]
        code, _ = self.api_request("POST", "/api/decide", {
            "model": "laya:en", "state": {"email": secret}, "questions": {}
        })
        self.assertEqual(200, code)
        totals, recents = self.mod.metrics_snapshot()
        self.assertEqual(old_count + 1, totals["requests"])
        self.assertEqual("success", recents[0]["outcome"])
        self.assertEqual("laya:en", recents[0]["model"])
        dashboard = self.mod.render_admin()
        self.assertIn("Runtime health and diagnostics", dashboard)
        self.assertIn("0.13.0-test", dashboard)
        self.assertIn("laya:en", dashboard)
        self.assertNotIn(secret, dashboard)
        self.assertLessEqual(len(recents), 25)

    def test_failed_upstream_response_is_reported_in_metrics(self):
        prev = self.mod.metrics_snapshot()[0]["upstream_errors"]
        code, _ = self.api_request("POST", "/api/decide", {
            "model": "fail:inference", "state": "x", "questions": {}
        })
        self.assertEqual(503, code)
        metrics, recent = self.mod.metrics_snapshot()
        self.assertEqual(prev + 1, metrics["upstream_errors"])
        self.assertEqual("upstream_error", recent[0]["outcome"])

    def test_broken_client_socket_does_not_trigger_second_503(self):
        """Regression for duplicate BrokenPipeError traces in v0.1.4."""
        before = self.mod.metrics_snapshot()[0]["client_disconnects"]
        original_response = self.mod.APIHandler.response
        calls = []

        def broken_response(handler, code, *args, **kwargs):
            calls.append(code)
            raise BrokenPipeError(32, "synthetic client disconnect")

        with patch.object(self.mod.APIHandler, "response", broken_response):
            conn = http.client.HTTPConnection("127.0.0.1", self.api.server_port, timeout=5)
            conn.request("POST", "/api/decide",
                         body=json.dumps({"model": "laya:en", "state": "hi", "questions": {}}),
                         headers={"Authorization": "Bearer " + self.mod.API_KEY,
                                  "Content-Type": "application/json"})
            try:
                conn.getresponse()
            except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError):
                pass
            conn.close()
        deadline = time.monotonic() + 2
        while self.mod.metrics_snapshot()[0]["client_disconnects"] == before and time.monotonic() < deadline:
            time.sleep(.01)
        metrics, recent = self.mod.metrics_snapshot()
        self.assertEqual(before + 1, metrics["client_disconnects"])
        self.assertEqual("client_disconnected", recent[0]["outcome"])
        self.assertEqual([200], calls, "No bogus second 503 should be attempted")

    def test_management_disabled_blocks_remove_at_server_and_hides_button(self):
        previous = self.mod.CONFIG["model_downloads_enabled"]
        self.mod.CONFIG["model_downloads_enabled"] = False
        try:
            count = len(MockOllaya.deletes)
            code, raw = self.admin_request("POST", "/remove", "model=decima%3Asmall&csrf=" + self.mod.CSRF)
            self.assertEqual(400, code)
            self.assertIn(b"Model management is disabled", raw)
            self.assertEqual(count, len(MockOllaya.deletes))
            page = self.mod.render_admin()
            self.assertNotIn('action="remove"', page)
            self.assertIn('action="select"', page)
            self.assertNotIn('action="pull"', page)
        finally:
            self.mod.CONFIG["model_downloads_enabled"] = previous

    def test_management_enabled_allows_remove_nonselected(self):
        previous = self.mod.CONFIG["model_downloads_enabled"]
        self.mod.CONFIG["model_downloads_enabled"] = True
        try:
            code, raw = self.admin_request("POST", "/remove", "model=decima%3Asmall&csrf=" + self.mod.CSRF)
            self.assertEqual(303, code, raw)
            self.assertEqual("decima:small", MockOllaya.deletes[-1])
            self.assertIn('action="pull"', self.mod.render_admin())
        finally:
            self.mod.CONFIG["model_downloads_enabled"] = previous

    def test_language_detection_and_query_selection(self):
        lang, explicit = self.mod.select_language("/", {"Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8"})
        self.assertEqual(("fr", False), (lang, explicit))
        self.assertEqual(("en", True), self.mod.select_language("/?lang=en", {"Accept-Language": "fr"}))
        self.assertEqual(("fr", False), self.mod.select_language("/", {"Cookie": "ollaya_ha_lang=fr"}))
        self.assertEqual(("en", False), self.mod.select_language("/", {"Accept-Language": "de-DE"}))
        self.assertIn("Gestion des modèles", self.mod.render_admin("fr"))
        self.assertIn("Santé du moteur et diagnostics", self.mod.render_admin("fr"))
        self.assertIn("Model management", self.mod.render_admin("en"))
        self.assertNotIn('action="remove"', self.mod.render_admin("fr"))

    def test_browser_language_and_cookie_persist_on_ingress(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.ui.server_port, timeout=5)
        conn.request("GET", "/?lang=fr", headers={"Accept-Language": "en-US"})
        response = conn.getresponse()
        self.assertEqual(200, response.status)
        cookie = response.getheader("Set-Cookie")
        self.assertIn("ollaya_ha_lang=fr", cookie)
        self.assertIn("Gestionnaire de modèles Ollaya", response.read().decode("utf-8"))
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", self.ui.server_port, timeout=5)
        conn.request("GET", "/", headers={"Accept-Language": "en-US", "Cookie": cookie.split(";", 1)[0]})
        response = conn.getresponse()
        self.assertEqual(200, response.status)
        self.assertIn("Gestion des modèles", response.read().decode("utf-8"))
        conn.close()

    def test_language_preserved_across_form_redirect(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.ui.server_port, timeout=5)
        fields = urlencode({"csrf": self.mod.CSRF, "model": "laya:en", "lang": "fr"})
        conn.request("POST", "/select", fields, {"Content-Type": "application/x-www-form-urlencoded"})
        response = conn.getresponse()
        self.assertEqual(303, response.status)
        self.assertEqual("./?lang=fr", response.getheader("Location"))
        response.read()
        conn.close()

    def test_localization_catalog_and_ha_options_complete(self):
        import re
        root = ROOT / "ollaya"
        en = json.loads((root / "i18n" / "en.json").read_text(encoding="utf-8"))
        fr = json.loads((root / "i18n" / "fr.json").read_text(encoding="utf-8"))
        self.assertEqual(set(en), set(fr))
        schema = (root / "config.yaml").read_text(encoding="utf-8").split("schema:", 1)[1]
        keys = set(re.findall(r"^  ([a-z][a-z_]+):", schema, flags=re.M))
        self.assertIn("model_downloads_enabled", keys)
        self.assertNotIn("model_management_enabled", keys)
        for locale in ("en", "fr"):
            yaml_text = (root / "translations" / (locale + ".yaml")).read_text(encoding="utf-8")
            config_part = yaml_text.split("configuration:\n", 1)[1].split("network:\n", 1)[0]
            translated = set(re.findall(r"^  ([a-z][a-z_]+):", config_part, re.M))
            self.assertEqual(keys, translated)
            self.assertIn("11435/tcp:", yaml_text)
        for file in ("DOCS.md", "docs/fr.md"):
            self.assertTrue((root / file).exists())
        self.assertIn("ghcr.io/ollaya-dev/ollaya:latest", (root / "Dockerfile").read_text())

    def test_select_and_reset(self):
        code, _ = self.admin_request("POST", "/select", "model=laya%3Aen&csrf=" + self.mod.CSRF)
        self.assertEqual(303, code)
        self.assertEqual("laya:en", self.mod.selected_model())
        self.assertTrue((Path(self.temp.name) / "selected_model.txt").exists())
        code, _ = self.admin_request("POST", "/reset", "csrf=" + self.mod.CSRF)
        self.assertEqual(303, code)
        self.assertFalse((Path(self.temp.name) / "selected_model.txt").exists())


if __name__ == "__main__":
    unittest.main()
